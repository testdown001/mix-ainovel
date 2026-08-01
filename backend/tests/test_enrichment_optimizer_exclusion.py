"""enrichment × optimizer 互斥判定（7 月整改遗留 #19，2026-08-01 修）。

原实现在 optimizer 执行**之前**一次算死互斥：
    enrichment_enabled = config.enable_enrichment and not optimizer_enabled
于是漏掉两种情形：

1. **optimizer 被时间预算跳过** —— 互斥的前提（optimizer 会跑）根本没成立，
   而 `optimizer_enabled` 是在跳过分支里才置回 False 的，此时 `enrichment_enabled`
   早已算成 False → **两步都不跑**。旁边的 polish 有对称的降级处理，enrichment 被漏了。
2. **optimizer 跑完但产出低于字数下限** —— optimizer 是「改写增益」不是「扩写」，
   density 只压不扩，于是 premium 档偏短章节全流程无任何补救。

两处都改成「跑完再复检」。互斥本身保留：optimizer 正常产出达标时 enrichment 不该叠加。
"""
from types import SimpleNamespace

import pytest

import app.models  # noqa: F401  触发 mapper 注册（含 user_quota）
from app.services.standard_post_processing_service import StandardPostProcessingService

MIN_WORDS = 2000
MAX_WORDS = 4000


class _FakeOrchestrator:
    """记录哪些后处理步骤真的被调用过，并可控制 optimizer 的产出长度。"""

    def __init__(self, optimizer_output_len: int = MIN_WORDS + 500):
        self.session = SimpleNamespace()
        self.llm_service = SimpleNamespace()
        self.prompt_service = SimpleNamespace()
        self.calls: list[str] = []
        self._optimizer_output_len = optimizer_output_len

    async def _run_optimizer(self, content, **kwargs):
        self.calls.append("optimizer")
        return "优" * self._optimizer_output_len, {"applied": True}

    async def _run_enrichment(self, content, **kwargs):
        self.calls.append("enrichment")
        return content + "扩写", {"applied": True}

    async def _run_polish(self, content, **kwargs):
        self.calls.append("polish")
        return content, {"applied": True}

    async def _run_density_compression(self, content, **kwargs):
        self.calls.append("density")
        return content, {"applied": True}


def _config(**overrides):
    base = dict(
        enable_self_critique=False,
        enable_consistency=False,
        enable_humanization=False,
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=False,
        enable_optimizer=True,
        enable_polish=False,
        enable_enrichment=True,
        enable_density_compression=False,
        enable_six_dimension=False,
        humanization_threshold=70,
        six_dimension_min_score=70,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


async def _run(orch, config, deadline=None, content="正" * (MIN_WORDS + 500)):
    summaries: dict = {}
    await StandardPostProcessingService(orch).run(
        best_content=content,
        best_version={"content": content, "metadata": {}},
        ai_review_result=None,
        review_summaries=summaries,
        config=config,
        project_id="proj-1",
        chapter_number=3,
        chapter_mission={"pov": "林玄"},
        writer_blueprint={"characters": []},
        history_context={"previous_summary": "上章摘要", "completed_chapters": []},
        user_id=1,
        chapter_word_count_min=MIN_WORDS,
        chapter_word_count_max=MAX_WORDS,
        chapter_target_word_count=3000,
        enhanced_flow=True,
        outline_title="第三章",
        forbidden_characters=[],
        allowed_new_characters=[],
        deadline=deadline,
    )
    return summaries


# ---------------------------------------------------------------------------
# 互斥本身：正常情况下两步不叠加
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrichment_skipped_when_optimizer_output_is_long_enough():
    """optimizer 正常跑且产出达标 → enrichment 不叠加（互斥保留，不是把它删了）。"""
    orch = _FakeOrchestrator(optimizer_output_len=MIN_WORDS + 800)
    await _run(orch, _config())
    assert orch.calls == ["optimizer"]


# ---------------------------------------------------------------------------
# 漏网 1：optimizer 被预算跳过
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrichment_runs_when_optimizer_skipped_for_budget_but_budget_allows():
    """optimizer 因预算跳过后，enrichment 不该被连坐——互斥前提已不成立。

    这里给的预算刚好卡在「optimizer 不够跑、但仍在同一判定档」的同一个 deadline 上：
    两步用同一个 _over_budget 阈值，所以预算不足时 enrichment 也会被跳过并**如实计入**
    skipped_for_budget（而非像修复前那样连记录都没有，静默消失）。
    """
    import time as _time

    orch = _FakeOrchestrator()
    summaries = await _run(orch, _config(), deadline=_time.perf_counter() + 1.0)

    assert orch.calls == []  # 预算确实不够，两步都没跑
    skipped = (summaries.get("time_budget") or {}).get("skipped") or []
    assert "optimizer" in skipped
    # 关键：enrichment 被显式记为「因预算跳过」，而不是因为互斥被静默判死
    assert "enrichment" in skipped


# ---------------------------------------------------------------------------
# 漏网 2（#19 本体）：optimizer 产出偏短
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrichment_rescues_short_optimizer_output():
    """optimizer 产出低于字数下限 → enrichment 兜底扩写（density 只压不扩，此前无救）。"""
    orch = _FakeOrchestrator(optimizer_output_len=MIN_WORDS - 600)
    summaries = await _run(orch, _config())

    assert orch.calls == ["optimizer", "enrichment"]
    assert summaries["enrichment"]["trigger"] == "below_min_after_optimizer"


@pytest.mark.asyncio
async def test_no_rescue_when_enrichment_switch_is_off():
    """兜底只对开了 enrichment 的档位生效，不擅自替用户开新步骤。"""
    orch = _FakeOrchestrator(optimizer_output_len=MIN_WORDS - 600)
    await _run(orch, _config(enable_enrichment=False))
    assert orch.calls == ["optimizer"]


@pytest.mark.asyncio
async def test_rescue_is_noop_without_min_word_count():
    """未配置字数下限时不做长度判定（避免 0 阈值把每章都拖进 enrichment）。"""
    orch = _FakeOrchestrator(optimizer_output_len=10)
    summaries: dict = {}
    await StandardPostProcessingService(orch).run(
        best_content="正文",
        best_version={"content": "正文", "metadata": {}},
        ai_review_result=None,
        review_summaries=summaries,
        config=_config(),
        project_id="p", chapter_number=1, chapter_mission={},
        writer_blueprint={"characters": []},
        history_context={"previous_summary": "", "completed_chapters": []},
        user_id=1,
        chapter_word_count_min=0,          # 未配置
        chapter_word_count_max=MAX_WORDS,
        chapter_target_word_count=3000,
        enhanced_flow=True, outline_title="t",
        forbidden_characters=[], allowed_new_characters=[], deadline=None,
    )
    assert orch.calls == ["optimizer"]
