from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

from sqlalchemy import select

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..models.novel import Chapter

logger = logging.getLogger(__name__)


class BatchGenerationService:
    """封装批量章节生成调度。"""

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

        try:
            parallel_workers = int(
                flow_config.get(
                    "batch_parallel_workers",
                    getattr(settings, "writer_batch_parallel_workers", 1),
                )
            )
        except (TypeError, ValueError):
            parallel_workers = 1
        parallel_workers = max(1, min(8, parallel_workers))

        existing_generated: set[int] = set()
        try:
            async with AsyncSessionLocal() as dependency_session:
                stmt = (
                    select(Chapter.chapter_number)
                    .where(Chapter.project_id == project_id)
                    .where(Chapter.chapter_number < max_requested)
                    .where(Chapter.selected_version_id.is_not(None))
                )
                rows = await dependency_session.execute(stmt)
                existing_generated = {int(num) for num in rows.scalars().all()}
        except Exception as exc:
            logger.warning("批量依赖预扫描失败，将回退为保守依赖计算: %s", exc)

        dependencies = BatchGenerationService._build_dependency_map(sorted_numbers, existing_generated)
        dependents: Dict[int, List[int]] = {}
        for chapter_number, dependency in dependencies.items():
            if dependency is not None:
                dependents.setdefault(dependency, []).append(chapter_number)

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

        ready = [num for num in sorted_numbers if dependencies.get(num) is None]
        ready.sort()
        running: Dict[asyncio.Task, int] = {}
        results_by_chapter: Dict[int, Dict[str, object]] = {}
        remaining = set(sorted_numbers)

        while remaining:
            while ready and len(running) < parallel_workers:
                chapter_number = ready.pop(0)
                if chapter_number not in remaining:
                    continue
                task = asyncio.create_task(_generate_one(chapter_number))
                running[task] = chapter_number

            if not running:
                fallback = min(remaining)
                logger.warning("批量调度出现空转，回退执行章节 %s", fallback)
                ready.append(fallback)
                continue

            done, _ = await asyncio.wait(set(running.keys()), return_when=asyncio.FIRST_COMPLETED)
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

                for dependent in dependents.get(chapter_number, []):
                    if dependent in remaining:
                        ready.append(dependent)
                ready.sort()

        return [results_by_chapter[num] for num in sorted_numbers]

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
