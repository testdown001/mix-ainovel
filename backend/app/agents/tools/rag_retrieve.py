# AIMETA P=RAG检索工具|R=向量相似度检索|NR=包装ChapterContextService|E=RagRetrieveTool|X=internal|A=工具实现|D=asyncio
"""RAG retrieval tool wrapping ChapterContextService."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class RagRetrieveTool(AgentTool):
    definition = ToolDefinition(
        name="rag_retrieve",
        description=(
            "Retrieve relevant context from the novel's knowledge base via vector similarity search. "
            "Returns matching text chunks and chapter summaries for a given query."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query_text": {
                    "type": "string",
                    "description": "The search query describing what context to retrieve.",
                },
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Multiple search queries for broader retrieval (optional, overrides query_text).",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5).",
                },
                "retrieval_mode": {
                    "type": "string",
                    "enum": ["vector", "hybrid"],
                    "description": "Retrieval mode: 'vector' (default) or 'hybrid'.",
                },
            },
            "required": ["query_text"],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.chapter_context_service import ChapterContextService
        from ...services.llm_service import LLMService

        try:
            llm_service = LLMService(context.session)
            vector_store = None
            from ...core.config import settings
            if settings.vector_store_enabled:
                from ...services.vector_store_service import VectorStoreService
                vector_store = VectorStoreService()

            svc = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

            queries = args.get("queries")
            top_k = args.get("top_k", 5)
            mode = args.get("retrieval_mode", "vector")

            if queries and len(queries) > 1:
                result = await svc.retrieve_multi_query(
                    project_id=context.project_id,
                    queries=queries,
                    user_id=context.user_id,
                    top_k_chunks=top_k,
                    retrieval_mode=mode,
                )
            else:
                query_text = queries[0] if queries else args["query_text"]
                result = await svc.retrieve_for_generation(
                    project_id=context.project_id,
                    query_text=query_text,
                    user_id=context.user_id,
                    top_k_chunks=top_k,
                    retrieval_mode=mode,
                )

            chunks = []
            for c in getattr(result, "chunks", []):
                chunks.append({
                    "content": getattr(c, "content", str(c)),
                    "score": getattr(c, "score", 0.0),
                    "source": getattr(c, "source", ""),
                })

            summaries = []
            for s in getattr(result, "summaries", []):
                summaries.append({
                    "content": getattr(s, "content", str(s)),
                    "chapter": getattr(s, "chapter_number", None),
                })

            return ToolResult(
                success=True,
                data={"chunks": chunks, "summaries": summaries, "total": len(chunks) + len(summaries)},
            )
        except Exception as e:
            logger.error("RagRetrieveTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))
