"""润色被合并进 optimizer 时的如实上报回归。

standard 分支在 optimizer 开启时把润色合并进同一次 LLM 调用。此前无论 optimizer
成败都写死 polish={"applied": True} —— optimizer 失败会原样返回入参文本，
一个字都没改，却报成润色已交付，用户那 5 积分的附加费就永远退不回来了。
"""
import asyncio
from types import SimpleNamespace

from app.services.generation_billing_service import polish_undelivered
from app.services.standard_post_processing_service import StandardPostProcessingService


class _FakeOrchestrator:
    """只实现本用例会走到的那一个后处理步骤。"""

    def __init__(self, optimizer_report):
        self._optimizer_report = optimizer_report
        self.optimizer_calls = []

    async def _run_optimizer(self, content, *, user_id, include_polish, include_density, max_word_count):
        self.optimizer_calls.append({"include_polish": include_polish})
        if self._optimizer_report.get("applied") is False:
            return content, self._optimizer_report  # 失败：原样返回入参文本
        return content + "（已优化）", self._optimizer_report


def _config():
    """只开 optimizer + polish，其余后处理全关，把测试收敛到合并分支。"""
    return SimpleNamespace(
        enable_self_critique=False,
        enable_consistency=False,
        enable_humanization=False,
        enable_optimizer=True,
        enable_enrichment=False,
        enable_polish=True,
        enable_density_compression=False,
        enable_six_dimension=False,
        six_dimension_min_score=70,
        # stage_b 异步分析参数（本用例不校验，给默认值让 run 能装配出来）
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=True,
    )


def _run(optimizer_report):
    orch = _FakeOrchestrator(optimizer_report)
    svc = StandardPostProcessingService(orch)
    return asyncio.run(
        svc.run(
            best_content="正文" * 500,
            best_version={"metadata": {"guardrail": {}}},
            ai_review_result=None,
            review_summaries={},
            config=_config(),
            project_id="p1",
            chapter_number=1,
            chapter_mission=None,
            writer_blueprint={},
            history_context={"previous_summary": ""},
            user_id=1,
            chapter_word_count_min=1000,
            chapter_word_count_max=4000,
            chapter_target_word_count=2000,
            enhanced_flow=None,
            outline_title="t",
            forbidden_characters=[],
            allowed_new_characters=[],
        )
    )


def test_merged_polish_reported_undelivered_when_optimizer_fails():
    result = _run({"steps": [], "applied": False, "error": "Error code: 401"})
    polish = result["review_summaries"]["polish"]
    assert polish["applied"] is False
    assert polish["reason"] == "optimizer_failed"
    # 计费侧据此退还附加费
    assert polish_undelivered(result) is True


def test_merged_polish_reported_delivered_when_optimizer_succeeds():
    # optimizer 成功时的真实结构里没有 applied 键，不能被误判成失败
    result = _run({"steps": [{"dimension": "comprehensive+polish", "notes": "ok"}]})
    polish = result["review_summaries"]["polish"]
    assert polish["applied"] is True
    assert polish["merged_into_optimizer"] is True
    assert polish_undelivered(result) is False


def test_polish_is_actually_merged_into_optimizer_call():
    orch = _FakeOrchestrator({"steps": []})
    svc = StandardPostProcessingService(orch)
    asyncio.run(
        svc.run(
            best_content="正文" * 500,
            best_version={"metadata": {"guardrail": {}}},
            ai_review_result=None,
            review_summaries={},
            config=_config(),
            project_id="p1",
            chapter_number=1,
            chapter_mission=None,
            writer_blueprint={},
            history_context={"previous_summary": ""},
            user_id=1,
            chapter_word_count_min=1000,
            chapter_word_count_max=4000,
            chapter_target_word_count=2000,
            enhanced_flow=None,
            outline_title="t",
            forbidden_characters=[],
            allowed_new_characters=[],
        )
    )
    assert orch.optimizer_calls == [{"include_polish": True}]
