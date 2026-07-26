"""W3 批次回归：refine 重打分回退 / 硬截断护尾 / 质量检测 prompt 去重 / 降级语义。

- auto_refiner 应用 combined_revision 后追加一次六维重打分：新分低于原分回退
  refine 前文本（reverted=True）；新分不低于原分保留并记 new_score；超时间预算
  跳过重打分直接保留 refine 结果（rescore=skipped_for_budget）。
- hard_trim_to_limit 始终保留最后一段（章尾钩子铁律），单段超限退化为句号切但保留末句。
- 质量检测 prompt 抽为共享常量 QUALITY_DETECTION_PROMPT_TEMPLATE，两处调用点
  同一对象且不含 \\r。
- _run_optimizer 失败静默返回补 applied:False + error；polish/density 失败路径
  已带 applied:False，一并锁定。
"""
from types import SimpleNamespace

import pytest

import app.models  # noqa: F401  触发 mapper 注册（含 user_quota）
from app.services import generation_analysis_task_service as gats_module
from app.services import pipeline_review as pipeline_review_module
from app.services.pipeline_review import PipelineReviewMixin
from app.services.six_dimension_review_service import SixDimensionReviewService
from app.services.standard_post_processing_service import StandardPostProcessingService
from app.services.text_compression_service import TextCompressionService


# ---------------------------------------------------------------------------
# 1. refine 后重打分回退
# ---------------------------------------------------------------------------

class _FakeOrchestrator:
    """仅实现六维路径覆盖到的重写步骤。"""

    def __init__(self):
        self.session = SimpleNamespace()
        self.llm_service = SimpleNamespace()
        self.prompt_service = SimpleNamespace()
        self.revision_calls: list[dict] = []

    async def _run_combined_revision(self, chapter_content=None, **kwargs):
        self.revision_calls.append({"chapter_content": chapter_content, **kwargs})
        return chapter_content + "·已重写", {"applied": True}


def _config(min_score: int = 70):
    return SimpleNamespace(
        enable_self_critique=False,
        enable_consistency=False,
        enable_humanization=False,
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=False,
        enable_optimizer=False,
        enable_polish=False,
        enable_enrichment=False,
        enable_density_compression=False,
        enable_six_dimension=True,
        humanization_threshold=70,
        six_dimension_min_score=min_score,
    )


async def _run_postprocess(orch, config, deadline=None):
    svc = StandardPostProcessingService(orch)
    return await svc.run(
        best_content="正文",
        best_version={"content": "正文", "metadata": {}},
        ai_review_result=None,
        review_summaries={},
        config=config,
        project_id="proj-1",
        chapter_number=3,
        chapter_mission={"pov": "林玄"},
        writer_blueprint={"characters": []},
        history_context={"previous_summary": "上章摘要", "completed_chapters": []},
        user_id=1,
        chapter_word_count_min=2000,
        chapter_word_count_max=4000,
        chapter_target_word_count=3000,
        enhanced_flow=True,
        outline_title="第三章",
        forbidden_characters=[],
        allowed_new_characters=[],
        deadline=deadline,
    )


def _review_payload(score: int):
    """低分且带 critical issue，足以触发 auto_refiner。"""
    return {
        "overall_score": score,
        "dimensions": {
            "internal_consistency": {
                "score": score,
                "issues": [
                    {
                        "severity": "critical",
                        "description": "主角动机断裂",
                        "location": "第二幕",
                        "suggestion": "补铺垫",
                    },
                ],
            },
        },
        "summary": "整体节奏拖沓",
    }


def _patch_review_sequence(monkeypatch, scores):
    """按调用顺序返回 scores 中的分数，记录每次调用入参。"""
    calls: list[dict] = []

    async def _fake_review(self, **kwargs):
        idx = min(len(calls), len(scores) - 1)
        calls.append(dict(kwargs))
        return _review_payload(scores[idx])

    monkeypatch.setattr(SixDimensionReviewService, "review_chapter", _fake_review)
    return calls


@pytest.mark.asyncio
async def test_rescore_lower_reverts_refine(monkeypatch):
    # 首评 60 触发 refine；重打分 50 < 60 → 回退 refine 前文本
    calls = _patch_review_sequence(monkeypatch, [60, 50])
    orch = _FakeOrchestrator()
    result = await _run_postprocess(orch, _config(min_score=70))

    assert len(calls) == 2  # 首评 + 重打分
    assert calls[1]["chapter_content"] == "正文·已重写"  # 重打分对象是 refine 后文本
    assert len(orch.revision_calls) == 1
    assert result["best_content"] == "正文"  # 已回退
    refiner = result["review_summaries"]["auto_refiner"]
    assert refiner["triggered"] is True
    assert refiner["reverted"] is True
    assert refiner["original_score"] == 60
    assert refiner["new_score"] == 50


@pytest.mark.asyncio
async def test_rescore_higher_keeps_refine(monkeypatch):
    # 首评 60 触发 refine；重打分 75 >= 60 → 保留 refine 结果并记 new_score
    calls = _patch_review_sequence(monkeypatch, [60, 75])
    orch = _FakeOrchestrator()
    result = await _run_postprocess(orch, _config(min_score=70))

    assert len(calls) == 2
    assert result["best_content"] == "正文·已重写"
    refiner = result["review_summaries"]["auto_refiner"]
    assert refiner["triggered"] is True
    assert refiner["new_score"] == 75
    assert "reverted" not in refiner


@pytest.mark.asyncio
async def test_rescore_skipped_when_over_budget(monkeypatch):
    # 六维块入场时预算尚足；refine 吃穿剩余预算后，重打分应被跳过、直接保留 refine 结果
    from app.services import standard_post_processing_service as spp_module

    class _Clock:
        def __init__(self):
            self.now = 0.0

        def perf_counter(self):
            return self.now

    clock = _Clock()
    monkeypatch.setattr(spp_module, "time", clock)

    calls = _patch_review_sequence(monkeypatch, [60, 90])

    class _SlowRefineOrchestrator(_FakeOrchestrator):
        async def _run_combined_revision(self, chapter_content=None, **kwargs):
            clock.now += 900  # refine 耗尽剩余预算（deadline=1000，单步预留 180s）
            return await super()._run_combined_revision(chapter_content=chapter_content, **kwargs)

    orch = _SlowRefineOrchestrator()
    result = await _run_postprocess(orch, _config(min_score=70), deadline=1000.0)

    assert len(calls) == 1  # 只有首评，重打分未发起
    assert result["best_content"] == "正文·已重写"  # 保留 refine 结果
    refiner = result["review_summaries"]["auto_refiner"]
    assert refiner["triggered"] is True
    assert refiner["rescore"] == "skipped_for_budget"
    assert "reverted" not in refiner


# ---------------------------------------------------------------------------
# 2. 硬截断保护章尾
# ---------------------------------------------------------------------------

def test_hard_trim_keeps_last_paragraph():
    tail = "章尾钩子：他终于推开了那扇门。"
    text = "开头段落。\n\n" + "中间灌水内容。" * 20 + "\n\n" + tail
    trimmed = TextCompressionService.hard_trim_to_limit(text, 40)

    assert tail in trimmed  # 末段（章尾钩子）必须保留
    assert len(trimmed) <= 40
    assert trimmed.endswith(tail)


def test_hard_trim_single_paragraph_keeps_last_sentence():
    # 单段仍超限：句号切退化，但末句必须保留
    text = "早句。" + "灌" * 30 + "。末句钩子。"
    trimmed = TextCompressionService.hard_trim_to_limit(text, 15)

    assert trimmed.endswith("末句钩子。")
    assert len(trimmed) <= 15
    assert trimmed == "早句。末句钩子。"  # 头部按句号边界回收 + 末句拼接


def test_hard_trim_noop_below_limit():
    text = "第一段。\n\n第二段。"
    assert TextCompressionService.hard_trim_to_limit(text, 100) == text


# ---------------------------------------------------------------------------
# 3. 质量检测 prompt 去重
# ---------------------------------------------------------------------------

def test_quality_detection_prompt_shared_and_no_cr():
    # 两处调用点引用同一模块级常量（逐字一致由同一对象保证）
    assert (
        gats_module.QUALITY_DETECTION_PROMPT_TEMPLATE
        is pipeline_review_module.QUALITY_DETECTION_PROMPT_TEMPLATE
    )
    template = pipeline_review_module.QUALITY_DETECTION_PROMPT_TEMPLATE
    assert "\r" not in template
    # 快照锁定关键内容（除 \r 外与去重前一致）
    assert template.startswith("你是一位资深网文质量分析师。请分析以下章节的三个维度，输出JSON。")
    assert "### 1. 爽点密度" in template
    assert "### 2. 模式重复" in template
    assert "### 3. 阶段性胜利 (Milestone Victory)" in template
    assert "[本章开头300字]\n{opening_300}" in template
    assert "[本章结尾300字]\n{ending_300}" in template
    assert "[本章预期]\n{expected_beat}" in template
    assert "[近期章节开头对比]\n{recent_patterns}" in template
    assert (
        '{{"coolpoint_score": 0, "coolpoint_moments": [], "coolpoint_issue": "", '
        '"repetition_score": 0, "repetition_issues": [], "within_chapter_repetition": [], '
        '"milestone_victory_detected": false, "milestone_description": ""}}'
    ) in template


@pytest.mark.asyncio
async def test_run_quality_detection_renders_shared_prompt():
    captured: dict = {}

    class _LLM:
        async def get_llm_response(self, *, system_prompt, conversation_history, **kwargs):
            captured["prompt"] = conversation_history[0]["content"]
            return '{"coolpoint_score": 7, "repetition_score": 8}'

    obj = PipelineReviewMixin()
    obj.llm_service = _LLM()
    result = await obj._run_quality_detection(
        "正文内容" * 100,
        chapter_number=5,
        chapter_mission={"macro_beat_description": "决战序幕", "satisfaction_design": {"type": "扮猪吃虎"}},
        previous_chapters_openings=["前章开头A"],
        user_id=1,
    )

    prompt = captured["prompt"]
    assert "\r" not in prompt
    assert "决战序幕" in prompt
    assert "扮猪吃虎" in prompt
    assert "第1个近期章节开头：前章开头A" in prompt
    assert prompt.startswith("你是一位资深网文质量分析师")
    # format 后双大括号收敛为单层 JSON 示例
    assert '{"coolpoint_score": 0' in prompt
    assert result["coolpoint_score"] == 7


# ---------------------------------------------------------------------------
# 4. 降级语义：失败静默返回带机器可判读标记
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_optimizer_failure_returns_applied_false():
    class _BoomLLM:
        async def get_llm_response(self, **kwargs):
            raise RuntimeError("通道超时")

    obj = PipelineReviewMixin()
    obj.llm_service = _BoomLLM()
    content, report = await obj._run_optimizer("原文", user_id=1)

    assert content == "原文"
    assert report["applied"] is False
    assert "通道超时" in report["error"]
    assert report["steps"] == []


@pytest.mark.asyncio
async def test_polish_failure_returns_applied_false():
    class _BoomLLM:
        async def get_optimize_llm_response(self, **kwargs):
            raise RuntimeError("润色通道不可用")

    obj = PipelineReviewMixin()
    obj.llm_service = _BoomLLM()
    content, report = await obj._run_polish("原文", user_id=1)

    assert content == "原文"
    assert report["applied"] is False


@pytest.mark.asyncio
async def test_density_compression_failure_returns_applied_false():
    class _BoomLLM:
        async def get_llm_response(self, **kwargs):
            raise RuntimeError("压缩通道不可用")

    async def _get_prompt(name):
        return "压缩指令"

    obj = PipelineReviewMixin()
    obj.llm_service = _BoomLLM()
    obj.prompt_service = SimpleNamespace(get_prompt=_get_prompt)
    content, report = await obj._run_density_compression("原文", user_id=1)

    assert content == "原文"
    assert report["applied"] is False
