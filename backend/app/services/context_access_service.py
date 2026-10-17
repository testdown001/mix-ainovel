from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..models.project_memory import ProjectMemory
from .chapter_context_service import ChapterContextService
from .evidence_router_service import EvidenceRouterService
from .memory_layer_service import MemoryLayerService


class ContextAccessService:
    """统一封装上下文访问逻辑，供编排器和兼容层复用。"""

    def __init__(self, session, llm_service, prompt_service):
        self.session = session
        self.llm_service = llm_service
        self.prompt_service = prompt_service
        self.evidence_router = EvidenceRouterService()

    async def get_rag_context(
        self,
        *,
        project_id: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        user_id: int,
        retrieval_mode: str = "vector",
        chapter_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not settings.vector_store_enabled:
            return {"chunks": [], "summaries": []}

        from .writer_shared import create_vector_store_or_none

        vector_store = create_vector_store_or_none()
        if vector_store is None:
            return {"chunks": [], "summaries": []}

        query_parts = [outline_title, outline_summary]
        if writing_notes:
            query_parts.append(writing_notes)
        rag_query = "\n".join(part for part in query_parts if part)

        context_service = ChapterContextService(llm_service=self.llm_service, vector_store=vector_store)
        rag_context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=rag_query or outline_title or outline_summary,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
            before_chapter=chapter_number,
        )
        return rag_context.to_payload()

    async def get_project_memory_text(self, project_id: str) -> Optional[str]:
        result = await self.session.execute(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        memory = result.scalars().first()
        return self._format_project_memory_text(memory)

    async def prefetch_project_memory_text(self, project_id: str, *, chapter_number: Optional[int] = None) -> Optional[str]:
        async with AsyncSessionLocal() as bg_session:
            result = await bg_session.execute(
                select(ProjectMemory).where(ProjectMemory.project_id == project_id)
            )
            memory = result.scalars().first()
            if chapter_number is not None:
                # Legacy global_summary/plot_arcs have no per-version provenance.
                # Use only a separately verified aggregate rather than leaking the
                # latest full-book state into an earlier chapter.
                from .book_summary_service import BookSummaryService
                summary = await BookSummaryService(bg_session, None).get_book_summary(
                    project_id, before_chapter=chapter_number,
                )
                return f"### 全书脉络\n{summary}" if summary else None
            return self._format_project_memory_text(memory)

    async def get_memory_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        involved_characters: List[str],
    ) -> str:
        memory_layer = MemoryLayerService(self.session, self.llm_service, self.prompt_service)
        return await memory_layer.get_memory_context(project_id, chapter_number, involved_characters)

    @staticmethod
    def format_filtered_context(filtered: Any) -> Optional[str]:
        return EvidenceRouterService.format_filtered_context(filtered)

    @staticmethod
    def _format_project_memory_text(memory: Any) -> Optional[str]:
        if not memory:
            return None

        parts = []
        if getattr(memory, "global_summary", None):
            parts.append(f"### 全局摘要\n{memory.global_summary}")
        if getattr(memory, "plot_arcs", None):
            parts.append("### 剧情线追踪\n" + json.dumps(memory.plot_arcs, ensure_ascii=False, indent=2))
        if getattr(memory, "story_timeline_summary", None):
            parts.append(f"### 叙事记忆摘要\n{memory.story_timeline_summary}")
        if not parts:
            return None
        return "\n\n".join(parts)
