# AIMETA P=生成写入后台任务服务_后处理与持久化|R=后处理_记忆更新_伏笔落库|NR=不含路由|E=GenerationWriteTaskService|X=internal|A=后台写入|D=sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..db.session import AsyncSessionLocal
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class GenerationWriteTaskService:
    """封装后台写入与更新任务。"""

    async def run_chapter_batch_post_processors(
        self,
        *,
        project_id: str,
        chapters: List[Dict[str, Any]],
        user_id: int,
    ) -> None:
        """批量正文交付后串行补齐摘要、向量和长程摘要。

        单章选版仍立即处理；批量生成则把这些非关键模型调用集中到正文全部完成后，
        避免多个后台任务与下一章正文同时占用模型通道。每章处理本身是降级型，某章
        失败不会阻断后续章节。
        """
        latest_by_number: Dict[int, str] = {}
        for item in chapters:
            try:
                chapter_number = int(item.get("chapter_number"))
            except (TypeError, ValueError):
                continue
            content = str(item.get("content") or "")
            if content:
                latest_by_number[chapter_number] = content

        logger.info(
            "开始批量章节后处理 project=%s chapters=%s",
            project_id,
            sorted(latest_by_number),
        )
        for chapter_number in sorted(latest_by_number):
            await self.run_chapter_post_processor(
                project_id=project_id,
                chapter_number=chapter_number,
                content=latest_by_number[chapter_number],
                user_id=user_id,
            )

        try:
            await CacheService.invalidate_project_schema_safely(project_id)
        except Exception:
            logger.warning("批量后处理完成后刷新项目缓存失败", exc_info=True)

        logger.info(
            "批量章节后处理完成 project=%s count=%d",
            project_id,
            len(latest_by_number),
        )

    async def _enqueue_current(
        self, *, project_id: str, chapter_number: int, user_id: int,
        content: str | None = None, kind: str | None = None, character_names=None,
    ) -> None:
        """Legacy facade: persist work, never mutate canon from a recommended draft."""
        import hashlib
        from .chapter_derivation_service import ChapterDerivationService, build_source_ref
        async with AsyncSessionLocal() as session:
            source = await build_source_ref(session, project_id=project_id, chapter_number=chapter_number)
            if source is None or (content is not None and source.source_content_hash !=
                                  hashlib.sha256(content.encode()).hexdigest()):
                logger.info("跳过非采用正文的派生任务 project=%s chapter=%s", project_id, chapter_number)
                return
            await ChapterDerivationService(session).enqueue_for_adoption(
                source, user_id=user_id, profile={"character_names": character_names or []},
                only_kinds=[kind] if kind else None,
            )
            await session.commit()

    async def run_chapter_post_processor(self, *, project_id: str, chapter_number: int,
                                         content: str, user_id: int) -> None:
        await self._enqueue_current(project_id=project_id, chapter_number=chapter_number,
                                    content=content, user_id=user_id)

    async def run_memory_update(self, *, project_id: str, chapter_number: int, chapter_content: str,
                                character_names: List[str], user_id: int) -> None:
        await self._enqueue_current(project_id=project_id, chapter_number=chapter_number,
                                    content=chapter_content, user_id=user_id, kind="memory",
                                    character_names=character_names)

    async def run_state_update(self, *, project_id: str, chapter_number: int, chapter_content: str,
                               character_names: List[str], user_id: int) -> None:
        await self._enqueue_current(project_id=project_id, chapter_number=chapter_number,
                                    content=chapter_content, user_id=user_id, kind="state",
                                    character_names=character_names)

    async def run_foreshadowing_extraction(self, *, project_id: str, chapter_id: int,
                                          chapter_number: int, chapter_content: str, user_id: int) -> None:
        await self._enqueue_current(project_id=project_id, chapter_number=chapter_number,
                                    content=chapter_content, user_id=user_id, kind="foreshadowing")

    async def run_character_significance(self, *, project_id: str, chapter_number: int,
                                         chapter_content: str, character_names: list, user_id: int) -> None:
        await self._enqueue_current(project_id=project_id, chapter_number=chapter_number,
                                    content=chapter_content, user_id=user_id, kind="character_significance",
                                    character_names=character_names)

    async def run_volume_retrospective(self, *, project_id: str, chapter_number: int, user_id: int) -> None:
        await self._enqueue_current(project_id=project_id, chapter_number=chapter_number,
                                    user_id=user_id, kind="volume_retrospective")

    async def run_outline_revision(self, *, project_id: str, chapter_number: int,
                                   chapter_content: str, user_id: int) -> None:
        await self._enqueue_current(project_id=project_id, chapter_number=chapter_number,
                                    content=chapter_content, user_id=user_id, kind="outline_revision")
