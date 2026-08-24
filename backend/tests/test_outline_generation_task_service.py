from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.novel import ChapterOutline
import app.services.outline_generation_task_service as task_service_module
from app.services.outline_generation_task_service import (
    OutlineGenerationTaskService,
    chunk_consecutive,
)


def test_chunk_consecutive_splits_gaps_and_respects_limit():
    assert chunk_consecutive([1, 2, 3, 11, 12, 13], limit=2) == [
        (1, 2),
        (3, 3),
        (11, 12),
        (13, 13),
    ]


@pytest.mark.asyncio
async def test_outline_task_lifecycle_and_failed_retry(db_session):
    service = OutlineGenerationTaskService(db_session)
    task = await service.create_task(
        project_id="project-1",
        user_id=7,
        chapter_numbers=range(7, 12),
        estimated_total_chapters=100,
        user_prompt="保留悬疑主线",
    )

    assert task.status == "queued"
    assert task.chapter_numbers == [7, 8, 9, 10, 11]
    assert (await service.get_active_task("project-1", 7)).id == task.id

    with pytest.raises(ValueError) as duplicate:
        await service.create_task(
            project_id="project-1",
            user_id=7,
            chapter_numbers=[12],
        )
    assert str(duplicate.value) == task.id

    task.status = "partial"
    task.completed_numbers = [7, 8, 9]
    task.failed_numbers = [10, 11]
    await db_session.commit()

    retry = await service.create_retry_task(task)
    assert retry.chapter_numbers == [10, 11]
    assert retry.total_chapters == 2
    assert retry.user_prompt == "保留悬疑主线"


@pytest.mark.asyncio
async def test_cancel_only_marks_future_batches(db_session):
    service = OutlineGenerationTaskService(db_session)
    task = await service.create_task(
        project_id="project-2",
        user_id=8,
        chapter_numbers=[1, 2, 3],
    )
    task.status = "running"
    await db_session.commit()

    cancelled = await service.request_cancel(task)
    assert cancelled.cancel_requested is True
    assert cancelled.status == "cancelling"
    assert "当前批次" in cancelled.message


@pytest.mark.asyncio
async def test_background_runner_persists_real_batch_progress(db_session, monkeypatch):
    service = OutlineGenerationTaskService(db_session)
    task = await service.create_task(
        project_id="project-3",
        user_id=9,
        chapter_numbers=range(7, 19),
    )
    session_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    monkeypatch.setattr(task_service_module, "AsyncSessionLocal", session_factory)
    generated_ranges = []

    async def fake_generate_range(*, session, project_id, start_chapter, num_chapters, **_kwargs):
        generated_ranges.append((start_chapter, start_chapter + num_chapters - 1))
        for number in range(start_chapter, start_chapter + num_chapters):
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=number,
                    sort_key=number * 1000,
                    title=f"第{number}章",
                    summary="测试章纲",
                )
            )
        await session.commit()

    await OutlineGenerationTaskService.run_background(task.id, fake_generate_range)
    await db_session.refresh(task)

    assert generated_ranges == [(7, 16), (17, 18)]
    assert task.status == "completed"
    assert task.progress_percent == 100
    assert task.completed_numbers == list(range(7, 19))
    assert task.failed_numbers == []
