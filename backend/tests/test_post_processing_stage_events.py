"""后处理链的分步阶段事件。

这条链是 6-10 次顺序 LLM 调用，约占一章生成四成时长，而在此之前它对前端**完全静默**：
最后一条阶段事件停在「多版本生成中」，用户盯着不动的进度条一分多钟，只能理解为卡死。
这里锁住：每个实际执行的步骤都在**开工时**发一条事件（发在结束时等于永远显示上一步），
被跳过的步骤不发，事件带的中文名不是机器名。
"""
import asyncio
from typing import Any, Dict, List, Tuple

import pytest

from app.services.standard_post_processing_service import (
    POST_STAGE_LABELS,
    StandardPostProcessingService,
)


class _Config:
    def __init__(self, **kwargs):
        defaults = dict(
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
            humanization_threshold=70,
            six_dimension_min_score=70,
        )
        defaults.update(kwargs)
        for key, value in defaults.items():
            setattr(self, key, value)


class _Orchestrator:
    """只实现被测路径会碰到的几个后处理动作，全部原样返回文本。"""

    def __init__(self):
        self.session = None
        self.llm_service = None
        self.prompt_service = None
        self.guardrails = None

    async def _run_combined_revision(self, content, **kwargs):
        return content, {"applied": True}

    async def _run_consistency_check(self, **kwargs):
        return kwargs["chapter_text"], {"applied": True}

    async def _run_optimizer(self, content, **kwargs):
        return content, {"applied": True}

    async def _run_polish(self, content, **kwargs):
        return content, {"applied": True}

    async def _run_enrichment(self, content, **kwargs):
        return content, {"applied": True}


async def _run(config: _Config, *, deadline=None) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    events: List[Tuple[str, str]] = []

    async def _emit(stage: str, message: str) -> None:
        events.append((stage, message))

    service = StandardPostProcessingService(_Orchestrator())
    result = await service.run(
        best_content="正文内容。" * 200,
        best_version={"metadata": {}},
        ai_review_result={"flaws": ["问题"], "suggestions": "建议"},
        review_summaries={},
        config=config,
        project_id="p1",
        chapter_number=1,
        chapter_mission=None,
        writer_blueprint={},
        history_context={"previous_summary": "", "completed_chapters": []},
        user_id=1,
        chapter_word_count_min=100,
        chapter_word_count_max=5000,
        chapter_target_word_count=3000,
        enhanced_flow=None,
        outline_title="第一章",
        forbidden_characters=[],
        allowed_new_characters=[],
        deadline=deadline,
        emit_stage=_emit,
    )
    return events, result


def test_each_executed_step_announces_itself():
    events, result = asyncio.run(
        _run(_Config(enable_consistency=True, enable_polish=True))
    )
    keys = [key for key, _ in events]
    assert keys == ["post_combined_revision", "post_consistency", "post_polish"]
    # 计时与事件同源：报了几步就该有几步的耗时
    assert set(result["stage_timings_ms"]) == set(keys)


def test_event_labels_are_human_readable():
    events, _ = asyncio.run(_run(_Config(enable_consistency=True)))
    for key, label in events:
        assert label == POST_STAGE_LABELS[key]
        assert not label.isascii(), f"{key} 的文案应是中文，而不是机器名"


def test_disabled_steps_stay_silent():
    events, _ = asyncio.run(_run(_Config()))
    assert [key for key, _ in events] == ["post_combined_revision"]


def test_budget_skipped_steps_stay_silent():
    """被时间预算跳过的步骤不发事件——报了却没跑，进度条会先跳后停。"""
    import time

    events, _ = asyncio.run(
        _run(
            _Config(enable_consistency=True, enable_polish=True),
            deadline=time.perf_counter() + 1,  # 远小于单步 180s 预留
        )
    )
    # polish 是付费必交付项，不受预算跳过；其余步骤全部静默
    assert [key for key, _ in events] == ["post_polish"]


def test_emit_stage_is_optional():
    """异步/批量路径不传 emit_stage 时不能炸。"""

    async def _go():
        service = StandardPostProcessingService(_Orchestrator())
        return await service.run(
            best_content="正文内容。" * 200,
            best_version={"metadata": {}},
            ai_review_result=None,
            review_summaries={},
            config=_Config(enable_consistency=True),
            project_id="p1",
            chapter_number=1,
            chapter_mission=None,
            writer_blueprint={},
            history_context={"previous_summary": "", "completed_chapters": []},
            user_id=1,
            chapter_word_count_min=100,
            chapter_word_count_max=5000,
            chapter_target_word_count=3000,
            enhanced_flow=None,
            outline_title="第一章",
            forbidden_characters=[],
            allowed_new_characters=[],
        )

    result = asyncio.run(_go())
    assert "post_consistency" in result["stage_timings_ms"]
