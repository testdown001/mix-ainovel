import asyncio
from unittest.mock import AsyncMock

from app.services.generation_write_task_service import GenerationWriteTaskService


def test_batch_post_processors_are_deduplicated_and_run_in_chapter_order(monkeypatch):
    service = GenerationWriteTaskService()
    process = AsyncMock()
    invalidate = AsyncMock()
    monkeypatch.setattr(service, "run_chapter_post_processor", process)
    monkeypatch.setattr(
        "app.services.generation_write_task_service.CacheService.invalidate_project_schema_safely",
        invalidate,
    )

    asyncio.run(
        service.run_chapter_batch_post_processors(
            project_id="project-1",
            chapters=[
                {"chapter_number": 8, "content": "第八章旧稿"},
                {"chapter_number": 7, "content": "第七章"},
                {"chapter_number": 8, "content": "第八章定稿"},
                {"chapter_number": 9, "content": ""},
            ],
            user_id=12,
        )
    )

    assert [call.kwargs["chapter_number"] for call in process.await_args_list] == [7, 8]
    assert process.await_args_list[1].kwargs["content"] == "第八章定稿"
    invalidate.assert_awaited_once_with("project-1")
