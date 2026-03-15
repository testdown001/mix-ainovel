from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from ..core.config import settings
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
        )
        return {
            "chunks": rag_context.chunk_texts() if rag_context.chunks else [],
            "summaries": rag_context.summary_lines() if rag_context.summaries else [],
        }

    async def get_two_stage_rag_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        writing_notes: str,
        pov_character: Optional[str],
        user_id: int,
        retrieval_mode: str = "vector",
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        routed = await self.evidence_router.route_two_stage(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            writing_notes=writing_notes,
            pov_character=pov_character,
            retrieval_mode=retrieval_mode,
            session=self.session,
            llm_service=self.llm_service,
            vector_store=None,
        )
        return routed.get("knowledge_context") or None, dict(routed.get("stats") or {})

    async def get_project_memory_text(self, project_id: str) -> Optional[str]:
        result = await self.session.execute(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        memory = result.scalars().first()
        if not memory:
            return None

        parts = []
        if memory.global_summary:
            parts.append(f"### 全局摘要\n{memory.global_summary}")
        if memory.plot_arcs:
            parts.append("### 剧情线追踪\n" + json.dumps(memory.plot_arcs, ensure_ascii=False, indent=2))
        if not parts:
            return None
        return "\n\n".join(parts)

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
