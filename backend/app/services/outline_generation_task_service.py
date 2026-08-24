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
GenerateChapterBody = Callable[..., Awaitable[Any]]


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
        generate_chapters: bool = False,
        chapter_generation_config: Optional[dict] = None,
        outline_completed_numbers: Optional[Iterable[int]] = None,
    ) -> OutlineGenerationTask:
        existing = await self.get_active_task(project_id, user_id)
        if existing:
            raise ValueError(existing.id)

        numbers = sorted(set(int(number) for number in chapter_numbers))
        if not numbers:
            raise ValueError("empty")
        precompleted = sorted(
            set(int(number) for number in (outline_completed_numbers or [])) & set(numbers)
        )

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
            completed_numbers=precompleted,
            failed_numbers=[],
            generate_chapters=generate_chapters,
            chapter_generation_config=(chapter_generation_config or None),
            body_completed_numbers=[],
            body_failed_numbers=[],
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
        task.message = "将在当前步骤完成后停止后续生成"
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def create_retry_task(
        self,
        source: OutlineGenerationTask,
    ) -> OutlineGenerationTask:
        outline_failed = set(source.failed_numbers or [])
        body_failed = set(source.body_failed_numbers or [])
        retry_numbers = sorted(outline_failed | body_failed)
        if source.status not in TERMINAL_STATUSES or not retry_numbers:
            raise ValueError("not_retryable")
        return await self.create_task(
            project_id=source.project_id,
            user_id=source.user_id,
            chapter_numbers=retry_numbers,
            estimated_total_chapters=source.estimated_total_chapters,
            user_prompt=source.user_prompt,
            generate_chapters=source.generate_chapters,
            chapter_generation_config=source.chapter_generation_config,
            # 正文失败说明章纲已经可用，重试时不重复调用章纲模型。
            outline_completed_numbers=body_failed - outline_failed,
        )

    @staticmethod
    async def run_background(
        task_id: str,
        generate_range: GenerateRange,
        generate_chapter_body: Optional[GenerateChapterBody] = None,
    ) -> None:
        """执行“章纲 → 可选正文”两阶段任务，并把逐章进度持久化。"""
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
            body_completed = set(task.body_completed_numbers or [])
            body_failed = set(task.body_failed_numbers or [])
            pending_outlines = set(task.chapter_numbers or []) - completed
            chunks = chunk_consecutive(sorted(pending_outlines))
            outline_weight = 50 if task.generate_chapters else 100

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
                task.progress_percent = min(
                    outline_weight,
                    round(processed / max(1, task.total_chapters) * outline_weight),
                )
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

            # 第二阶段只处理章纲成功落库的章节；失败章纲留给重试，不拿空规划写正文。
            if (
                task.generate_chapters
                and completed
                and not task.cancel_requested
                and task.status != "cancelled"
            ):
                body_targets = sorted(completed)
                body_started = time.monotonic()

                if generate_chapter_body is None:
                    body_failed.update(set(body_targets) - body_completed)
                    task.error_message = "正文生成器未配置"
                else:
                    for index, chapter_number in enumerate(body_targets):
                        if chapter_number in body_completed:
                            continue
                        await session.refresh(task)
                        if task.cancel_requested:
                            task.status = "cancelled"
                            task.stage = "cancelled"
                            task.message = "已停止尚未开始的正文生成"
                            break

                        task.status = "running"
                        task.stage = "body_generating"
                        task.current_body_chapter = chapter_number
                        task.message = (
                            f"章纲已完成，正在生成第 {chapter_number} 章正文 "
                            f"({len(body_completed) + len(body_failed) + 1}/{len(body_targets)})"
                        )
                        await session.commit()

                        permanent_failure = False
                        try:
                            outcome = await generate_chapter_body(
                                task_id=task.id,
                                project_id=task.project_id,
                                user_id=task.user_id,
                                chapter_number=chapter_number,
                                generation_config=task.chapter_generation_config or {},
                            )
                            if isinstance(outcome, dict) and outcome.get("status") == "failed":
                                permanent_failure = bool(outcome.get("permanent"))
                                raise RuntimeError(str(outcome.get("error") or "正文生成失败"))
                            body_completed.add(chapter_number)
                            body_failed.discard(chapter_number)
                        except Exception as exc:  # 单章失败继续后续章；确定性失败直接停止空烧
                            await session.rollback()
                            task = await session.get(OutlineGenerationTask, task_id)
                            if task is None:
                                return
                            body_failed.add(chapter_number)
                            task.error_message = str(exc)[:2000]
                            logger.exception(
                                "章纲任务自动正文失败: task=%s chapter=%s",
                                task_id,
                                chapter_number,
                            )
                            if permanent_failure:
                                body_failed.update(
                                    number
                                    for number in body_targets[index + 1 :]
                                    if number not in body_completed
                                )

                        task.body_completed_numbers = sorted(body_completed)
                        task.body_failed_numbers = sorted(body_failed)
                        body_processed = len(body_completed) + len(body_failed)
                        task.progress_percent = min(
                            100,
                            50 + round(body_processed / max(1, task.total_chapters) * 50),
                        )
                        elapsed = max(1.0, time.monotonic() - body_started)
                        remaining = max(0, len(body_targets) - body_processed)
                        task.estimated_remaining_seconds = round(
                            elapsed / max(1, body_processed) * remaining
                        )
                        task.stage = "body_saving"
                        task.message = (
                            f"章纲 {len(completed)} / {task.total_chapters}，"
                            f"正文 {len(body_completed)} / {len(body_targets)}"
                        )
                        await session.commit()

                        if permanent_failure:
                            break

            await session.refresh(task)
            task.current_batch_start = None
            task.current_batch_end = None
            task.current_body_chapter = None
            task.estimated_remaining_seconds = 0
            task.completed_at = datetime.now(timezone.utc)

            outline_complete = len(completed) == task.total_chapters and not failed
            body_complete = (
                not task.generate_chapters
                or (len(body_completed) == task.total_chapters and not body_failed)
            )
            delivered_anything = bool(completed or body_completed)

            if task.status == "cancelled" or task.cancel_requested:
                task.status = "cancelled"
                task.stage = "cancelled"
                if task.generate_chapters:
                    task.message = (
                        f"任务已停止，章纲 {len(completed)} 章，正文 {len(body_completed)} 章"
                    )
                else:
                    task.message = f"任务已停止，完成 {len(completed)} / {task.total_chapters} 章"
            elif outline_complete and body_complete:
                task.status = "completed"
                task.stage = "completed"
                if task.generate_chapters:
                    task.message = f"{len(completed)} 章章纲与正文已全部生成"
                else:
                    task.message = f"{len(completed)} 章章纲已全部生成"
                task.progress_percent = 100
            elif delivered_anything:
                task.status = "partial"
                task.stage = "completed"
                if task.generate_chapters:
                    task.message = (
                        f"章纲完成 {len(completed)} 章，正文完成 {len(body_completed)} 章，"
                        f"{len(failed) + len(body_failed)} 章需要重试"
                    )
                else:
                    task.message = f"完成 {len(completed)} 章，{len(failed)} 章需要重试"
                task.progress_percent = 100
            else:
                task.status = "failed"
                task.stage = "failed"
                task.message = "章纲与正文生成失败，请重试" if task.generate_chapters else "章纲生成失败，请重试"
                task.progress_percent = 100

            await session.commit()
