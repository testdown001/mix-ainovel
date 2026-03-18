import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.generation_background_task_service import GenerationBackgroundTaskService


def test_generation_background_task_service_exposes_coroutine_methods():
    service = GenerationBackgroundTaskService()

    assert asyncio.iscoroutinefunction(service.run_chapter_post_processor)
    assert asyncio.iscoroutinefunction(service.run_stage_b_analyses)
    assert asyncio.iscoroutinefunction(service.run_six_dimension_review)
    assert asyncio.iscoroutinefunction(service.run_memory_update)
    assert asyncio.iscoroutinefunction(service.run_foreshadowing_extraction)


def test_generation_background_task_service_delegates_six_dimension_review():
    analysis_tasks = SimpleNamespace(
        run_six_dimension_review=AsyncMock(),
    )
    service = GenerationBackgroundTaskService(
        analysis_tasks=analysis_tasks,
        write_tasks=SimpleNamespace(),
    )

    asyncio.run(
        service.run_six_dimension_review(
            version_id=9,
            project_id="proj-1",
            chapter_number=3,
            chapter_title="测试章",
            chapter_content="正文",
            chapter_plan=None,
            previous_summary=None,
        )
    )

    analysis_tasks.run_six_dimension_review.assert_awaited_once()


def test_generation_background_task_service_delegates_memory_update():
    write_tasks = SimpleNamespace(
        run_memory_update=AsyncMock(),
    )
    service = GenerationBackgroundTaskService(
        analysis_tasks=SimpleNamespace(),
        write_tasks=write_tasks,
    )

    asyncio.run(
        service.run_memory_update(
            project_id="proj-1",
            chapter_number=8,
            chapter_content="正文",
            character_names=["林峰"],
            user_id=1,
        )
    )

    write_tasks.run_memory_update.assert_awaited_once()
