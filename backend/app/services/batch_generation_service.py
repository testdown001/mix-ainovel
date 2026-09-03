from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..models.novel import Chapter

logger = logging.getLogger(__name__)


class BatchGenerationService:
    """封装批量章节生成调度。"""

    @staticmethod
    def resolve_parallel_workers(flow_config: Optional[Dict[str, object]] = None) -> int:
        """解析批量并行数并收束到服务端安全范围。

        并行数只作用于没有前后文依赖的章节链；连续章节仍会被依赖图强制串行，
        因此提高默认工作数不会让相邻章节在缺少上一章正文时抢跑。
        """
        flow_config = flow_config or {}
        try:
            parallel_workers = int(
                flow_config.get(
                    "batch_parallel_workers",
                    getattr(settings, "writer_batch_parallel_workers", 1),
                )
            )
        except (TypeError, ValueError):
            parallel_workers = 1
        return max(1, min(8, parallel_workers))

    @staticmethod
    async def load_existing_generated_chapters(
        project_id: str,
        max_requested: int,
    ) -> set[int]:
        """加载目标章之前已经选版的章节，用于切分可并行的独立章节链。"""
        try:
            async with AsyncSessionLocal() as dependency_session:
                stmt = (
                    select(Chapter.chapter_number)
                    .where(Chapter.project_id == project_id)
                    .where(Chapter.chapter_number < max_requested)
                    .where(Chapter.selected_version_id.is_not(None))
                )
                rows = await dependency_session.execute(stmt)
                return {int(num) for num in rows.scalars().all()}
        except Exception as exc:
            logger.warning("批量依赖预扫描失败，将回退为保守依赖计算: %s", exc)
            return set()

    @staticmethod
    async def run_dependency_aware(
        *,
        chapter_numbers: List[int],
        existing_generated: set[int],
        parallel_workers: int,
        generate_one: Callable[[int], Awaitable[Dict[str, Any]]],
        on_started: Optional[Callable[[int, int, int], Awaitable[None]]] = None,
        on_completed: Optional[
            Callable[[int, Dict[str, Any], int, int], Awaitable[None]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """按前序依赖调度章节，并保证取消时收束所有子任务。

        ``existing_generated`` 会把批次切成互不依赖的章节链；链内严格串行，链间
        最多 ``parallel_workers`` 个并行。结果固定按章节号返回，便于计费与 UI 对齐。
        """
        sorted_numbers = sorted(set(chapter_numbers))
        if not sorted_numbers:
            return []

        dependencies = BatchGenerationService._build_dependency_map(
            sorted_numbers,
            existing_generated,
        )
        dependents: Dict[int, List[int]] = {}
        for chapter_number, dependency in dependencies.items():
            if dependency is not None:
                dependents.setdefault(dependency, []).append(chapter_number)

        ready = sorted(num for num in sorted_numbers if dependencies.get(num) is None)
        running: Dict[asyncio.Task, int] = {}
        results_by_chapter: Dict[int, Dict[str, Any]] = {}
        remaining = set(sorted_numbers)
        worker_limit = max(1, min(8, int(parallel_workers or 1)))

        try:
            while remaining:
                while ready and len(running) < worker_limit:
                    chapter_number = ready.pop(0)
                    if chapter_number not in remaining:
                        continue
                    if on_started is not None:
                        await on_started(
                            chapter_number,
                            len(running) + 1,
                            len(results_by_chapter),
                        )
                    task = asyncio.create_task(
                        generate_one(chapter_number),
                        name=f"batch-chapter-{chapter_number}",
                    )
                    running[task] = chapter_number

                if not running:
                    fallback = min(remaining)
                    logger.warning("批量调度出现空转，回退执行章节 %s", fallback)
                    ready.append(fallback)
                    continue

                done, _ = await asyncio.wait(
                    set(running.keys()),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    chapter_number = running.pop(task)
                    remaining.discard(chapter_number)
                    task_result = task.result()
                    results_by_chapter[chapter_number] = task_result

                    logger.info(
                        "批量生成: 章节 %s 完成 (%d/%d)",
                        chapter_number,
                        len(results_by_chapter),
                        len(sorted_numbers),
                    )
                    if on_completed is not None:
                        await on_completed(
                            chapter_number,
                            task_result,
                            len(results_by_chapter),
                            len(sorted_numbers),
                        )

                    for dependent in dependents.get(chapter_number, []):
                        if dependent in remaining:
                            ready.append(dependent)
                    ready.sort()
        finally:
            if running:
                for task in running:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*running, return_exceptions=True)

        return [results_by_chapter[num] for num in sorted_numbers]

    @staticmethod
    async def generate_chapter_batch(
        *,
        project_id: str,
        chapter_numbers: List[int],
        user_id: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, object]] = None,
    ) -> List[Dict[str, object]]:
        from .pipeline_orchestrator import PipelineOrchestrator

        sorted_numbers = sorted(set(chapter_numbers))
        if not sorted_numbers:
            return []

        flow_config = flow_config or {}
        max_requested = sorted_numbers[-1]
        parallel_workers = BatchGenerationService.resolve_parallel_workers(flow_config)
        existing_generated = await BatchGenerationService.load_existing_generated_chapters(
            project_id,
            max_requested,
        )

        async def _generate_one(chapter_number: int) -> Dict[str, object]:
            try:
                async with AsyncSessionLocal() as session:
                    orchestrator = PipelineOrchestrator(session)
                    result = await orchestrator.generate_chapter(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        user_id=user_id,
                        writing_notes=writing_notes,
                        flow_config=flow_config,
                    )
                    return {
                        "chapter_number": chapter_number,
                        "status": "success",
                        "result": result,
                    }
            except Exception as exc:
                logger.error("批量生成: 章节 %s 失败: %s", chapter_number, exc)
                return {
                    "chapter_number": chapter_number,
                    "status": "failed",
                    "error": str(exc)[:500],
                }

        return await BatchGenerationService.run_dependency_aware(
            chapter_numbers=sorted_numbers,
            existing_generated=existing_generated,
            parallel_workers=parallel_workers,
            generate_one=_generate_one,
        )

    @staticmethod
    def _build_dependency_map(
        chapter_numbers: List[int],
        existing_generated: set[int],
    ) -> Dict[int, Optional[int]]:
        dependencies: Dict[int, Optional[int]] = {}
        last_requested: Optional[int] = None

        for chapter_number in chapter_numbers:
            dependency: Optional[int] = None
            if last_requested is not None:
                nearest_existing = max((n for n in existing_generated if n < chapter_number), default=None)
                if nearest_existing is None or last_requested > nearest_existing:
                    dependency = last_requested
            dependencies[chapter_number] = dependency
            last_requested = chapter_number
        return dependencies
