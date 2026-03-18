# AIMETA P=风格指纹包装服务_跨章统计复用|R=风格指纹预取|NR=不含API路由|E=FingerprintService|X=internal|A=风格指纹|D=asyncio|S=compute|RD=./README.ai
from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional

from .author_fingerprint_service import AuthorFingerprintService

logger = logging.getLogger(__name__)


class FingerprintService:
    """包装风格指纹提取，屏蔽编排器中的线程调度细节。"""

    def __init__(self, fingerprint_service: Optional[AuthorFingerprintService] = None):
        self._fingerprint_service = fingerprint_service or AuthorFingerprintService()

    async def prefetch_fingerprint_context(
        self,
        *,
        project_id: str,
        project: Any,
        chapter_number: int,
    ) -> Optional[str]:
        try:
            return await asyncio.to_thread(
                self.build_fingerprint_context,
                project_id=project_id,
                project=project,
                chapter_number=chapter_number,
            )
        except Exception as exc:
            logger.warning("风格指纹提取失败（不影响生成）: %s", exc)
            return None

    def build_fingerprint_context(
        self,
        *,
        project_id: str,
        project: Any,
        chapter_number: int,
    ) -> Optional[str]:
        chapter_texts = self._collect_chapter_texts(project=project, chapter_number=chapter_number)
        if len(chapter_texts) < 3:
            logger.info(
                "项目 %s 风格指纹跳过：历史已定稿章节不足 (history_chapters=%s)",
                project_id,
                len(chapter_texts),
            )
            return None
        context = self._fingerprint_service.get_or_extract(project_id, chapter_texts)
        if context:
            logger.info(
                "项目 %s 已生成风格指纹上下文 (history_chapters=%s)",
                project_id,
                len(chapter_texts),
            )
        return context

    @staticmethod
    def _collect_chapter_texts(*, project: Any, chapter_number: int) -> List[str]:
        texts: List[str] = []
        for chapter in sorted(getattr(project, "chapters", []) or [], key=lambda item: item.chapter_number):
            if getattr(chapter, "chapter_number", 0) >= chapter_number:
                continue
            selected_version = getattr(chapter, "selected_version", None)
            content = getattr(selected_version, "content", None) if selected_version else None
            if content:
                texts.append(content)
        return texts
