"""灵感模式会员分档特性：门控 / 人格 / N路发散 / 档位推导。"""
import asyncio
import json

from app.core.feature_gating import tier_allows, tier_rank
from app.services.muse_persona import (
    build_persona_injection,
    is_valid_persona,
    list_personas,
)
from app.services.quota_service import QuotaService
from app.services.concept_divergence_service import ConceptDivergenceService


# ---------- 门控 ----------

def test_tier_rank_order():
    assert tier_rank("free") < tier_rank("creator") < tier_rank("flagship")


def test_feature_gating_matrix():
    assert not tier_allows("free", "muse_search")
    assert tier_allows("creator", "muse_search")
    assert tier_allows("creator", "muse_persona")
    assert not tier_allows("creator", "muse_divergence")
    assert tier_allows("flagship", "muse_divergence")
    assert tier_allows("flagship", "muse_search")


# ---------- 档位推导 ----------

def test_derive_tier_from_plan_name():
    from types import SimpleNamespace
    # 无显式 tier 时回退按名字猜
    assert QuotaService._derive_tier(SimpleNamespace(name="旗舰版", tier=None)) == "flagship"
    assert QuotaService._derive_tier(SimpleNamespace(name="创作者版", tier=None)) == "creator"
    assert QuotaService._derive_tier(None) == "creator"  # 通用付费默认 creator


def test_derive_tier_prefers_explicit_plan_tier():
    from types import SimpleNamespace
    # 后台显式配置的 tier 优先于名字（名字叫"免费版"但配成 flagship）
    assert QuotaService._derive_tier(SimpleNamespace(name="免费版", tier="flagship")) == "flagship"
    assert QuotaService._derive_tier(SimpleNamespace(name="随便", tier="creator")) == "creator"


def test_capabilities_for_tier_and_registry():
    from app.core.feature_gating import capabilities_for_tier, registry_dump, CAPABILITIES
    assert capabilities_for_tier("free") == []
    creator_keys = {c["key"] for c in capabilities_for_tier("creator")}
    assert creator_keys == {"muse_persona", "muse_search"}
    flagship_keys = {c["key"] for c in capabilities_for_tier("flagship")}
    assert "muse_divergence" in flagship_keys
    # 注册表元数据含展示名/说明（定价页与门控同源）
    reg = registry_dump()
    assert len(reg) == len(CAPABILITIES)
    assert all(r["label"] and r["description"] for r in reg)


def test_min_tier_override_changes_gating_and_capabilities():
    from app.core.feature_gating import tier_allows, capabilities_for_tier
    # 后台把 muse_divergence 覆写到 creator 档
    overrides = {"muse_divergence": "creator"}
    assert tier_allows("creator", "muse_divergence", overrides)
    assert "muse_divergence" in {c["key"] for c in capabilities_for_tier("creator", overrides)}
    # 默认（无覆写）creator 不含 divergence
    assert not tier_allows("creator", "muse_divergence")


def test_user_quota_effective_tier_falls_back_when_not_premium():
    from app.models.user_quota import UserQuota
    q = UserQuota(user_id=1, is_premium=False, plan_tier="flagship")
    assert q.effective_tier == "free"  # 非会员一律回落 free
    q2 = UserQuota(user_id=2, is_premium=True, premium_expires_at=None, plan_tier="flagship")
    assert q2.effective_tier == "flagship"


# ---------- 人格 ----------

def test_personas_list_and_injection():
    keys = {p["key"] for p in list_personas()}
    assert "default" in keys and "cyberpunk" in keys
    assert is_valid_persona("myth_epic")
    assert not is_valid_persona("不存在")
    # 默认人格不注入额外文案
    assert build_persona_injection("default") == ""
    # 具体人格注入含 SOUL 优先标记
    block = build_persona_injection("cyberpunk")
    assert "SOUL" in block and "赛博朋克" in block


# ---------- N路发散 ----------

def _make_divergence_service(gen_responses):
    svc = ConceptDivergenceService.__new__(ConceptDivergenceService)
    queue = list(gen_responses)

    async def _fake_generate(*args, **kwargs):
        return queue.pop(0)

    class _LLM:
        generate = staticmethod(_fake_generate)
    svc.llm_service = _LLM()
    return svc


def test_diverge_generates_scores_and_keeps_top():
    seeds_json = json.dumps([
        {"title": "A", "logline": "种子A", "hook": "钩A", "world": "w", "tone": "t", "twist": "x"},
        {"title": "B", "logline": "种子B", "hook": "钩B", "world": "w", "tone": "t", "twist": "y"},
        {"title": "C", "logline": "种子C", "hook": "钩C", "world": "w", "tone": "t", "twist": "z"},
    ], ensure_ascii=False)
    scores_json = json.dumps([
        {"id": 0, "novelty": 3, "marketability": 3, "coherence": 3, "verdict": "一般"},
        {"id": 1, "novelty": 9, "marketability": 8, "coherence": 9, "verdict": "强"},
        {"id": 2, "novelty": 6, "marketability": 6, "coherence": 6, "verdict": "中"},
    ], ensure_ascii=False)
    svc = _make_divergence_service([seeds_json, scores_json])
    out = asyncio.run(svc.diverge(seed_topic="一个守墓人", user_id=1, n=3, keep=2))
    assert len(out) == 2
    # Top1 应为 B（总分最高）
    assert out[0]["title"] == "B"
    assert out[0]["score"] == 26
    assert "verdict" in out[0]


def test_diverge_empty_topic_returns_empty():
    svc = _make_divergence_service([])
    assert asyncio.run(svc.diverge(seed_topic="  ", user_id=1)) == []


def test_diverge_handles_wrapped_array_and_scoring_failure():
    # 生成返回 {"seeds":[...]} 包裹；评分调用抛错 → 中性分兜底，不丢种子
    seeds_wrapped = json.dumps({"seeds": [
        {"title": "X", "logline": "种子X", "hook": "h", "world": "w", "tone": "t", "twist": "tw"},
    ]}, ensure_ascii=False)

    svc = ConceptDivergenceService.__new__(ConceptDivergenceService)
    calls = {"n": 0}

    async def _gen(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return seeds_wrapped
        raise RuntimeError("score model down")

    class _LLM:
        generate = staticmethod(_gen)
    svc.llm_service = _LLM()

    out = asyncio.run(svc.diverge(seed_topic="点子", user_id=1, n=3, keep=3))
    assert len(out) == 1
    assert out[0]["title"] == "X"
    assert out[0]["score"] == 15  # 评分失败 → 中性分 5+5+5
