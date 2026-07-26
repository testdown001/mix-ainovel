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
async def test_insufficient_budget_for_one_step_skips():
    # 仅剩 60s（< 单步预留 180s）：不足以再跑一整步，应跳过以防末步跑满 180s 冲破硬超时
    orch = _FakeOrchestrator()
    result = await _run(orch, deadline=time.perf_counter() + 60)
    assert orch.calls == []
    skipped = result["review_summaries"]["time_budget"]["skipped"]
    assert "combined_revision" in skipped
    assert "optimizer" in skipped


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


@pytest.mark.asyncio
async def test_budget_rechecked_between_steps(monkeypatch):
    # 步间复检：进入 polish/enrichment 段时预算尚足，polish 一步吃穿剩余预算后，
    # enrichment 应在自己启动前被复检拦下（此前四步只在段首查一次，连跑不复检）。
    from app.services import standard_post_processing_service as spp_module

    class _Clock:
        def __init__(self):
            self.now = 0.0

        def perf_counter(self):
            return self.now

    clock = _Clock()
    monkeypatch.setattr(spp_module, "time", clock)

    class _SlowPolishOrchestrator:
        def __init__(self):
            self.calls: list[str] = []

        async def _run_polish(self, content, **kwargs):
            self.calls.append("polish")
            clock.now += 900  # 该步耗尽剩余预算
            return content + "·已润色", {"applied": True}

        async def _run_enrichment(self, content, **kwargs):
            self.calls.append("enrichment")
            return content + "·已扩写", {"applied": True}

    config = _config()
    config.enable_optimizer = False
    config.enable_polish = True
    config.enable_enrichment = True

    orch = _SlowPolishOrchestrator()
    svc = StandardPostProcessingService(orch)
    result = await svc.run(
        best_content="正文",
        best_version={"content": "正文", "metadata": {}},
        ai_review_result=None,
        review_summaries={},
        config=config,
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
        deadline=1000.0,
    )

    # polish 启动时剩余 1000s 正常执行；enrichment 复检时仅剩 100s(<180s 单步预留) 被跳过
    assert orch.calls == ["polish"]
    assert result["review_summaries"]["time_budget"]["skipped"] == ["enrichment"]
    assert result["best_content"] == "正文·已润色"


@pytest.mark.asyncio
async def test_paid_polish_never_skipped_by_budget(monkeypatch):
    """付费必交付：enable_polish 只可能来自勾选付费（preset 不再强开），
    预算耗尽时 polish 仍执行，不进 skipped 列表。"""
    from app.services import standard_post_processing_service as spp_module

    class _Clock:
        def __init__(self):
            self.now = 0.0

        def perf_counter(self):
            return self.now

    clock = _Clock()
    monkeypatch.setattr(spp_module, "time", clock)

    class _Orch:
        def __init__(self):
            self.calls: list[str] = []

        async def _run_polish(self, content, **kwargs):
            self.calls.append("polish")
            return content + "·已润色", {"applied": True}

        async def _run_enrichment(self, content, **kwargs):
            self.calls.append("enrichment")
            return content + "·已扩写", {"applied": True}

    config = _config()
    config.enable_optimizer = False
    config.enable_polish = True
    config.enable_enrichment = True

    clock.now = 5000.0  # 进入后处理段时预算已彻底耗尽
    orch = _Orch()
    svc = StandardPostProcessingService(orch)
    result = await svc.run(
        best_content="正文",
        best_version={"content": "正文", "metadata": {}},
        ai_review_result=None,
        review_summaries={},
        config=config,
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
        deadline=1000.0,
    )

    assert "polish" in orch.calls
    assert "polish" not in result["review_summaries"].get("time_budget", {}).get("skipped", [])
    assert result["best_content"] == "正文·已润色"


@pytest.mark.asyncio
async def test_paid_polish_survives_optimizer_budget_skip(monkeypatch):
    """premium 勾选润色：optimizer 被预算跳过时润色降级为独立 polish 步执行，不白扣费。"""
    from app.services import standard_post_processing_service as spp_module

    class _Clock:
        def __init__(self):
            self.now = 5000.0  # 预算已耗尽

        def perf_counter(self):
            return self.now

    monkeypatch.setattr(spp_module, "time", _Clock())

    class _Orch:
        def __init__(self):
            self.calls: list[str] = []

        async def _run_optimizer(self, content, **kwargs):
            self.calls.append("optimizer")
            return content + "·已优化", {"applied": True}

        async def _run_polish(self, content, **kwargs):
            self.calls.append("polish")
            return content + "·已润色", {"applied": True}

    config = _config()
    config.enable_optimizer = True
    config.enable_polish = True

    orch = _Orch()
    svc = StandardPostProcessingService(orch)
    result = await svc.run(
        best_content="正文",
        best_version={"content": "正文", "metadata": {}},
        ai_review_result=None,
        review_summaries={},
        config=config,
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
        deadline=1000.0,
    )

    assert "optimizer" not in orch.calls
    assert "polish" in orch.calls
    assert "optimizer" in result["review_summaries"]["time_budget"]["skipped"]
    assert result["best_content"] == "正文·已润色"
