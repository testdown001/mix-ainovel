# AIMETA P=章纲后台任务服务|R=创建查询停止重试_批次执行_进度落库|NR=不负责单批章纲提示词|E=OutlineGenerationTaskService|X=internal|A=后台任务|D=sqlalchemy,asyncio|S=db|RD=./README.ai
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import AsyncSessionLocal
from ..models.novel import ChapterOutline
from ..models.outline_generation_task import OutlineGenerationTask

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running", "cancelling")
TERMINAL_STATUSES = ("completed", "partial", "failed", "cancelled")
OUTLINE_TASK_BATCH_SIZE = 10

GenerateRange = Callable[..., Awaitable[Any]]


def chunk_consecutive(numbers: Sequence[int], limit: int = OUTLINE_TASK_BATCH_SIZE) -> List[Tuple[int, int]]:
    """把章号拆成连续且不超过 limit 的闭区间，供首次生成和失败重试共用。"""
    ordered = sorted(set(int(number) for number in numbers))
    if not ordered:
        return []

    chunks: List[Tuple[int, int]] = []
    start = previous = ordered[0]
    for number in ordered[1:]:
        if number != previous + 1 or number - start + 1 > limit:
            chunks.append((start, previous))
            start = number
        previous = number
    chunks.append((start, previous))
    return chunks


class OutlineGenerationTaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_owned_task(
        self,
        task_id: str,
        *,
        project_id: str,
        user_id: int,
    ) -> Optional[OutlineGenerationTask]:
        result = await self.session.execute(
            select(OutlineGenerationTask).where(
                OutlineGenerationTask.id == task_id,
                OutlineGenerationTask.project_id == project_id,
                OutlineGenerationTask.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_task(self, project_id: str, user_id: int) -> Optional[OutlineGenerationTask]:
        result = await self.session.execute(
            select(OutlineGenerationTask)
            .where(
                OutlineGenerationTask.project_id == project_id,
                OutlineGenerationTask.user_id == user_id,
                OutlineGenerationTask.status.in_(ACTIVE_STATUSES),
            )
            .order_by(OutlineGenerationTask.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_task(
        self,
        *,
        project_id: str,
        user_id: int,
        chapter_numbers: Iterable[int],
        estimated_total_chapters: Optional[int] = None,
        user_prompt: Optional[str] = None,
    ) -> OutlineGenerationTask:
        existing = await self.get_active_task(project_id, user_id)
        if existing:
            raise ValueError(existing.id)

        numbers = sorted(set(int(number) for number in chapter_numbers))
        if not numbers:
            raise ValueError("empty")

        task = OutlineGenerationTask(
            id=str(uuid4()),
            project_id=project_id,
            user_id=user_id,
            status="queued",
            stage="queued",
            message="任务已进入后台队列",
            start_chapter=numbers[0],
            total_chapters=len(numbers),
            chapter_numbers=numbers,
            completed_numbers=[],
            failed_numbers=[],
            progress_percent=0,
            estimated_total_chapters=estimated_total_chapters,
            user_prompt=(user_prompt or "").strip() or None,
            cancel_requested=False,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def request_cancel(self, task: OutlineGenerationTask) -> OutlineGenerationTask:
        if task.status not in ACTIVE_STATUSES:
            return task
        task.cancel_requested = True
        task.status = "cancelling"
        task.stage = "cancelling"
        task.message = "将在当前批次完成后停止后续生成"
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def create_retry_task(
        self,
        source: OutlineGenerationTask,
    ) -> OutlineGenerationTask:
        failed = sorted(set(source.failed_numbers or []))
        if source.status not in TERMINAL_STATUSES or not failed:
            raise ValueError("not_retryable")
        return await self.create_task(
            project_id=source.project_id,
            user_id=source.user_id,
            chapter_numbers=failed,
            estimated_total_chapters=source.estimated_total_chapters,
            user_prompt=source.user_prompt,
        )

    @staticmethod
    async def run_background(task_id: str, generate_range: GenerateRange) -> None:
        """执行真实批次；每批提交任务状态，供其他应用副本轮询读取。"""
        run_started = time.monotonic()
        async with AsyncSessionLocal() as session:
            task = await session.get(OutlineGenerationTask, task_id)
            if task is None:
                logger.error("章纲后台任务不存在: %s", task_id)
                return

            task.status = "running"
            task.stage = "preparing"
            task.message = "正在准备世界蓝图和已有章纲"
            task.started_at = datetime.now(timezone.utc)
            await session.commit()

            completed = set(task.completed_numbers or [])
            failed = set(task.failed_numbers or [])
            chunks = chunk_consecutive(task.chapter_numbers or [])

            for batch_start, batch_end in chunks:
                await session.refresh(task)
                if task.cancel_requested:
                    task.status = "cancelled"
                    task.stage = "cancelled"
                    task.message = "已停止尚未开始的章纲批次"
                    break

                task.status = "running"
                task.stage = "generating"
                task.current_batch_start = batch_start
                task.current_batch_end = batch_end
                task.message = f"正在生成第 {batch_start}～{batch_end} 章章纲"
                await session.commit()

                expected = set(range(batch_start, batch_end + 1))
                try:
                    await generate_range(
                        session=session,
                        project_id=task.project_id,
                        user_id=task.user_id,
                        start_chapter=batch_start,
                        num_chapters=batch_end - batch_start + 1,
                        estimated_total_chapters=task.estimated_total_chapters,
                        user_prompt=task.user_prompt,
                    )
                    saved_result = await session.execute(
                        select(ChapterOutline.chapter_number).where(
                            ChapterOutline.project_id == task.project_id,
                            ChapterOutline.chapter_number.in_(expected),
                        )
                    )
                    saved = {int(number) for number in saved_result.scalars().all()}
                    completed.update(saved)
                    failed.update(expected - saved)
                except Exception as exc:  # 单批失败不阻断后续批次
                    await session.rollback()
                    task = await session.get(OutlineGenerationTask, task_id)
                    if task is None:
                        return
                    failed.update(expected)
                    task.error_message = str(exc)[:2000]
                    logger.exception(
                        "章纲后台任务批次失败: task=%s range=%s-%s",
                        task_id,
                        batch_start,
                        batch_end,
                    )

                # 同一个章号若实际已经落库，应从失败集合移除。
                failed.difference_update(completed)
                task.completed_numbers = sorted(completed)
                task.failed_numbers = sorted(failed)
                processed = len(completed) + len(failed)
                task.progress_percent = min(100, round(processed / max(1, task.total_chapters) * 100))
                elapsed = max(1.0, time.monotonic() - run_started)
                if processed:
                    remaining = max(0, task.total_chapters - processed)
                    task.estimated_remaining_seconds = round(elapsed / processed * remaining)
                task.stage = "saving"
                task.message = f"已完成 {len(completed)} / {task.total_chapters} 章"
                await session.commit()

            await session.refresh(task)
            task.current_batch_start = None
            task.current_batch_end = None
            task.estimated_remaining_seconds = 0
            task.completed_at = datetime.now(timezone.utc)

            if task.status == "cancelled" or task.cancel_requested:
                task.status = "cancelled"
                task.stage = "cancelled"
                task.message = f"任务已停止，完成 {len(completed)} / {task.total_chapters} 章"
            elif completed and failed:
                task.status = "partial"
                task.stage = "completed"
                task.message = f"完成 {len(completed)} 章，{len(failed)} 章需要重试"
                task.progress_percent = 100
            elif completed:
                task.status = "completed"
                task.stage = "completed"
                task.message = f"{len(completed)} 章章纲已全部生成"
                task.progress_percent = 100
            else:
                task.status = "failed"
                task.stage = "failed"
                task.message = "章纲生成失败，请重试"
                task.progress_percent = 100

            await session.commit()
