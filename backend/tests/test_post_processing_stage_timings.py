"""后处理链分步埋点。

改前：整条 6-10 次顺序 LLM 调用的链只有外层一个 stage_a_post_processing span，
线上实测它占一章总耗时的 39%（203s 中的 79s）却是一整块黑盒——想知道该优化哪一步，
只能去 llm.log 按时间戳手工对齐调用序列。同时 stage_timings_ms 这个字典声明了、
返回了，却从来没被写入过。这里锁住每步各有一条计时，且跳过的步骤不留假记录。
"""
import time
from types import SimpleNamespace

import pytest

from app.services.standard_post_processing_service import StandardPostProcessingService


class _FakeGuardrails:
    def check(self, **kwargs):
        return SimpleNamespace(passed=True)


class _FakeOrchestrator:
    """只实现后处理链会碰到的钩子，每个钩子原样返回文本并记录调用顺序。"""

    def __init__(self):
        self.calls: list[str] = []
        self.session = None
        self.llm_service = None
        self.prompt_service = None
        self.guardrails = _FakeGuardrails()

    async def _run_combined_revision(self, chapter_content=None, **kwargs):
        self.calls.append("combined_revision")
        return (chapter_content or "正文"), {"applied": True}

    async def _run_consistency_check(self, *, project_id, chapter_text, user_id):
        self.calls.append("consistency")
        return chapter_text, {"issues": 0}

    async def _run_optimizer(self, content, **kwargs):
        self.calls.append("optimizer")
        return content, {"applied": True}

    async def _run_polish(self, content, **kwargs):
        self.calls.append("polish")
        return content, {"applied": True}

    async def _run_enrichment(self, content, **kwargs):
        self.calls.append("enrichment")
        return content, {"applied": True}

    async def _run_density_compression(self, content, **kwargs):
        self.calls.append("density")
        return content, {"applied": True}


def _config(**overrides):
    base = dict(
        enable_self_critique=False,
        enable_consistency=False,
        enable_humanization=False,
        enable_optimizer=False,
        enable_polish=False,
        enable_enrichment=False,
        enable_density_compression=False,
        enable_six_dimension=False,
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=False,
        humanization_threshold=60,
        six_dimension_min_score=70,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


async def _run(config, *, mark_stage=None, ai_review_result=None, deadline=None, content=None):
    orch = _FakeOrchestrator()
    svc = StandardPostProcessingService(orch)
    result = await svc.run(
        # 默认正文长度要落在 [min, max*0.9) 区间内：低于 min 会触发 optimizer 后的
        # enrichment 兜底，高于 max*0.9 会触发密度压缩合并，都不是本文件要测的路径。
        best_content=content if content is not None else "第二天一开门，陈锈就听见街口吵。" * 80,
        best_version={"content": "x", "metadata": {}},
        ai_review_result=ai_review_result,
        review_summaries={},
        config=config,
        project_id="p1",
        chapter_number=2,
        chapter_mission={"pov": "陈锈"},
        writer_blueprint={"characters": []},
        history_context={"previous_summary": "前情", "completed_chapters": []},
        user_id=1,
        chapter_word_count_min=1000,
        chapter_word_count_max=4000,
        chapter_target_word_count=2500,
        enhanced_flow=False,
        outline_title="第二章",
        forbidden_characters=[],
        allowed_new_characters=[],
        deadline=deadline,
        mark_stage=mark_stage,
    )
    return orch, result


@pytest.mark.asyncio
class TestStageTimings:
    async def test_dict_no_longer_dead(self):
        """改前这个字典永远是空的，任何分步耗时都无从得知。"""
        _, result = await _run(_config(enable_consistency=True))
        assert result["stage_timings_ms"]["post_consistency"] >= 0

    async def test_each_step_recorded_once(self):
        config = _config(
            enable_self_critique=True,
            enable_consistency=True,
            enable_optimizer=True,
            enable_enrichment=True,
        )
        orch, result = await _run(config)
        timings = result["stage_timings_ms"]
        assert "post_combined_revision" in timings
        assert "post_consistency" in timings
        assert "post_optimizer" in timings
        # optimizer 开启时 enrichment 被互斥压制，不该留下计时
        assert "post_enrichment" not in timings
        assert orch.calls == ["combined_revision", "consistency", "optimizer"]

    async def test_enrichment_fallback_after_short_optimizer_output(self):
        """optimizer 产出低于字数下限时解除互斥、由 enrichment 兜底——这条兜底路径
        同样要有自己的计时，否则它的耗时会被算进 optimizer 头上。"""
        orch, result = await _run(
            _config(enable_optimizer=True, enable_enrichment=True),
            content="太短了。" * 10,
        )
        assert orch.calls == ["optimizer", "enrichment"]
        assert "post_optimizer" in result["stage_timings_ms"]
        assert "post_enrichment" in result["stage_timings_ms"]
        assert result["review_summaries"]["enrichment"]["trigger"] == "below_min_after_optimizer"

    async def test_polish_only_path(self):
        _, result = await _run(_config(enable_polish=True))
        assert "post_polish" in result["stage_timings_ms"]

    async def test_enrichment_without_optimizer(self):
        _, result = await _run(_config(enable_enrichment=True))
        assert "post_enrichment" in result["stage_timings_ms"]

    async def test_skipped_steps_leave_no_timing(self):
        """预算耗尽时步骤不执行，就不能留下一条 0ms 的假记录。"""
        past_deadline = time.perf_counter() - 1
        orch, result = await _run(
            _config(enable_self_critique=True, enable_consistency=True, enable_optimizer=True),
            deadline=past_deadline,
        )
        assert result["stage_timings_ms"] == {}
        assert orch.calls == []
        assert result["review_summaries"]["time_budget"]["exceeded"] is True

    async def test_disabled_steps_leave_no_timing(self):
        _, result = await _run(_config())
        assert result["stage_timings_ms"] == {}

    async def test_forwards_to_trace_span_emitter(self):
        """同一份计时既要填回字典，也要发 span 进 trace.log。"""
        seen: list[tuple[str, float]] = []
        _, result = await _run(
            _config(enable_consistency=True, enable_optimizer=True),
            mark_stage=lambda name, started: seen.append((name, started)),
        )
        assert [name for name, _ in seen] == ["post_consistency", "post_optimizer"]
        assert set(result["stage_timings_ms"]) == {"post_consistency", "post_optimizer"}

    async def test_works_without_mark_stage(self):
        """mark_stage 是可选的（Agent 桥等调用方不传），不能因此报错。"""
        _, result = await _run(_config(enable_consistency=True), mark_stage=None)
        assert "post_consistency" in result["stage_timings_ms"]

    async def test_combined_revision_triggered_by_review_flaws(self):
        _, result = await _run(
            _config(),
            ai_review_result={"flaws": ["节奏拖沓"], "suggestions": "收紧中段"},
        )
        assert "post_combined_revision" in result["stage_timings_ms"]
