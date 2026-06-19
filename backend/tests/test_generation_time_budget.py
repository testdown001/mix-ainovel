"""章节生成关键路径"时间预算 + 优雅降级"回归测试。

验证 StandardPostProcessingService：越过 deadline 时跳过剩余可选后处理步骤
(combined_revision / optimizer 等)、不再发起对应 LLM 调用，并在
review_summaries['time_budget'] 记录被跳过项；未越界时正常执行全部步骤。
锁定"超时不再全盘失败、而是带当前最佳稿按时返回"的行为。
"""
import time
from types import SimpleNamespace

import pytest

from app.services.standard_post_processing_service import StandardPostProcessingService


class _FakeOrchestrator:
    """只实现本测试覆盖到的两个后处理步骤，记录调用顺序。"""

    def __init__(self):
        self.calls: list[str] = []

    async def _run_combined_revision(self, content, **kwargs):
        self.calls.append("combined_revision")
        return content + "·已修订", {"applied": True}

    async def _run_optimizer(self, content, **kwargs):
        self.calls.append("optimizer")
        return content + "·已优化", {"applied": True}


def _config():
    # 仅开启 combined_revision(经 ai_review flaws 触发) 与 optimizer，
    # 其余重型步骤(一致性/人味化/六维/扩写/压缩)关闭以聚焦预算逻辑。
    return SimpleNamespace(
        enable_self_critique=False,
        enable_consistency=False,
        enable_humanization=False,
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=True,
        enable_optimizer=True,
        enable_polish=False,
        enable_density_compression=False,
        enable_enrichment=False,
        enable_six_dimension=False,
        humanization_threshold=80,
        six_dimension_min_score=70,
    )


async def _run(orch, deadline):
    svc = StandardPostProcessingService(orch)
    return await svc.run(
        best_content="正文",
        best_version={"content": "正文", "metadata": {}},
        ai_review_result={"flaws": ["缺陷"], "suggestions": "改进"},
        review_summaries={},
        config=_config(),
        project_id="p1",
        chapter_number=1,
        chapter_mission={"pov": "第三人称"},
        writer_blueprint={"characters": []},
        history_context={"previous_summary": "", "completed_chapters": []},
        user_id=1,
        chapter_word_count_min=1000,
        chapter_word_count_max=3000,
        chapter_target_word_count=2000,
        enhanced_flow=False,
        outline_title="标题",
        forbidden_characters=[],
        allowed_new_characters=[],
        deadline=deadline,
    )


@pytest.mark.asyncio
async def test_over_budget_skips_remaining_steps():
    orch = _FakeOrchestrator()
    result = await _run(orch, deadline=time.perf_counter() - 1)  # 已越界
    # 越界：两步都不应真正发起 LLM 调用
    assert orch.calls == []
    skipped = result["review_summaries"]["time_budget"]["skipped"]
    assert "combined_revision" in skipped
    assert "optimizer" in skipped
    # 返回的仍是有效正文(当前最佳稿)，未被改写
    assert result["best_content"] == "正文"


@pytest.mark.asyncio
async def test_within_budget_runs_all_steps():
    orch = _FakeOrchestrator()
    result = await _run(orch, deadline=time.perf_counter() + 10_000)  # 远未越界
    assert orch.calls == ["combined_revision", "optimizer"]
    assert "time_budget" not in result["review_summaries"]
    assert result["best_content"] == "正文·已修订·已优化"


@pytest.mark.asyncio
async def test_no_deadline_disables_budget():
    orch = _FakeOrchestrator()
    result = await _run(orch, deadline=None)  # 预算关闭
    assert orch.calls == ["combined_revision", "optimizer"]
    assert "time_budget" not in result["review_summaries"]
