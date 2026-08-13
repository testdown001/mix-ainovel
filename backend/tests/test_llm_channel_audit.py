"""llm_channel_audit 配置体检规则的回归测试。

核心契约：
1. 兜底与主通道「完全相同」→ error（2026-08-13 线上事故的直接教训）；
   仅同上游不同模型 → warn；不同上游 → 不报。
2. 兜底 base_url/model 留空时按回退到 llm.* 的实际值比较（留空≠不同）。
3. 无独立嵌入配置且主通道非 OpenAI 官方地址 → error（RAG 静默失效）。
4. 各级别排序：error 在前。
"""
import pytest

from app.models.system_config import SystemConfig
from app.services.llm_channel_audit import (
    _AUDIT_KEYS,
    audit_llm_config,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清掉审计键对应的环境变量，避免开发机/CI 环境污染断言。"""
    for key in _AUDIT_KEYS:
        monkeypatch.delenv(key.upper().replace(".", "_"), raising=False)


async def _seed(session, **kv):
    for key, value in kv.items():
        session.add(SystemConfig(key=key.replace("__", "."), value=value))
    await session.commit()


def _codes(findings):
    return [f["code"] for f in findings]


# ---------------------------------------------------------------- fallback


@pytest.mark.asyncio
async def test_fallback_identical_to_default_is_error(db_session):
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://api.vendor-a.com/v1",
        llm__model="gpt-x",
        llm_fallback__api_key="k2",
        llm_fallback__base_url="https://api.vendor-a.com/v1/",  # 仅尾斜杠差异
        llm_fallback__model="GPT-X",  # 仅大小写差异
    )
    findings = await audit_llm_config(db_session)
    assert "fallback_same_target" in _codes(findings)
    target = next(f for f in findings if f["code"] == "fallback_same_target")
    assert target["level"] == "error"


@pytest.mark.asyncio
async def test_fallback_blank_fields_inherit_default_still_error(db_session):
    """兜底 base_url/model 留空时运行时会回退 llm.*，审计必须按回退后的值判定。"""
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://api.vendor-a.com/v1",
        llm__model="gpt-x",
        llm_fallback__api_key="k2",  # base_url/model 均留空
    )
    findings = await audit_llm_config(db_session)
    assert "fallback_same_target" in _codes(findings)


@pytest.mark.asyncio
async def test_fallback_same_upstream_different_model_is_warn(db_session):
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://api.vendor-a.com/v1",
        llm__model="gpt-x",
        llm_fallback__api_key="k2",
        llm_fallback__model="claude-y",
    )
    findings = await audit_llm_config(db_session)
    codes = _codes(findings)
    assert "fallback_same_upstream" in codes
    assert "fallback_same_target" not in codes
    upstream = next(f for f in findings if f["code"] == "fallback_same_upstream")
    assert upstream["level"] == "warn"


@pytest.mark.asyncio
async def test_fallback_different_upstream_is_clean(db_session):
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://api.vendor-a.com/v1",
        llm__model="gpt-x",
        llm_fallback__api_key="k2",
        llm_fallback__base_url="https://api.vendor-b.com/v1",
        llm_fallback__model="gpt-x",
    )
    codes = _codes(await audit_llm_config(db_session))
    assert "fallback_same_target" not in codes
    assert "fallback_same_upstream" not in codes
    assert "fallback_disabled" not in codes


@pytest.mark.asyncio
async def test_fallback_unconfigured_is_info(db_session):
    await _seed(db_session, llm__api_key="k1", llm__base_url="https://api.openai.com/v1")
    findings = await audit_llm_config(db_session)
    disabled = next(f for f in findings if f["code"] == "fallback_disabled")
    assert disabled["level"] == "info"


# ---------------------------------------------------------------- embedding


@pytest.mark.asyncio
async def test_embedding_silently_disabled_on_third_party_base(db_session):
    """主通道是第三方中转地址且无独立嵌入配置 → get_embedding 会静默返回空向量。"""
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://relay.third-party.io/v1",
        llm__model="gpt-x",
    )
    findings = await audit_llm_config(db_session)
    emb = next(f for f in findings if f["code"] == "embedding_silently_disabled")
    assert emb["level"] == "error"


@pytest.mark.asyncio
async def test_embedding_ok_when_dedicated_config_present(db_session):
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://relay.third-party.io/v1",
        embedding__api_key="ek",
    )
    codes = _codes(await audit_llm_config(db_session))
    assert "embedding_silently_disabled" not in codes


@pytest.mark.asyncio
async def test_embedding_ok_on_official_openai_base(db_session):
    await _seed(db_session, llm__api_key="k1", llm__base_url="https://api.openai.com/v1")
    codes = _codes(await audit_llm_config(db_session))
    assert "embedding_silently_disabled" not in codes


@pytest.mark.asyncio
async def test_ollama_provider_without_url_is_warn(db_session):
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://api.openai.com/v1",
        embedding__provider="ollama",
    )
    findings = await audit_llm_config(db_session)
    ollama = next(f for f in findings if f["code"] == "ollama_embedding_url_missing")
    assert ollama["level"] == "warn"


# ---------------------------------------------------------------- 其余通道与排序


@pytest.mark.asyncio
async def test_default_unconfigured_is_error(db_session):
    findings = await audit_llm_config(db_session)
    assert findings[0]["code"] == "default_unconfigured"
    assert findings[0]["level"] == "error"


@pytest.mark.asyncio
async def test_optional_channels_reported_when_missing(db_session):
    await _seed(db_session, llm__api_key="k1", llm__base_url="https://api.openai.com/v1")
    codes = _codes(await audit_llm_config(db_session))
    assert "search_unconfigured" in codes
    assert "grader_unconfigured" in codes
    assert "polish_uses_default" in codes


@pytest.mark.asyncio
async def test_rerank_enabled_without_url_is_warn(db_session):
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://api.openai.com/v1",
        rerank__enabled="true",
    )
    codes = _codes(await audit_llm_config(db_session))
    assert "rerank_url_missing" in codes


@pytest.mark.asyncio
async def test_rerank_disabled_not_reported(db_session):
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://api.openai.com/v1",
        rerank__enabled="false",
    )
    codes = _codes(await audit_llm_config(db_session))
    assert "rerank_url_missing" not in codes


@pytest.mark.asyncio
async def test_findings_sorted_by_severity(db_session):
    """error 必须排在 warn/info 前面，前端直接按序渲染。"""
    await _seed(
        db_session,
        llm__api_key="k1",
        llm__base_url="https://relay.third-party.io/v1",
        llm__model="gpt-x",
        llm_fallback__api_key="k2",
    )
    findings = await audit_llm_config(db_session)
    levels = [f["level"] for f in findings]
    order = {"error": 0, "warn": 1, "info": 2}
    assert levels == sorted(levels, key=lambda l: order[l])
    assert levels[0] == "error"
