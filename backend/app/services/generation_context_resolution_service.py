# AIMETA P=生成上下文解析服务_预热结果消费|R=预热结果解析_RAG决议|NR=不含主流程编排|E=GenerationContextResolutionService|X=internal|A=上下文解析|D=asyncio|S=compute,db|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fastapi import HTTPException


@dataclass
class ResolvedPrefetchContext:
    enhanced_context: Dict[str, Any] = field(default_factory=dict)
    project_memory_text: Optional[str] = None
    rag_context: Optional[Dict[str, Any]] = None
    knowledge_context: Optional[str] = None
    rag_stats: Optional[Dict[str, Any]] = None
    writer_prompt: Optional[str] = None


class GenerationContextResolutionService:
    """统一消费预热任务结果，解析成生成阶段可直接使用的上下文。"""

    def __init__(
        self,
        *,
        evidence_router,
        generation_policy_service,
        llm_service,
        session,
    ):
        self.evidence_router = evidence_router
        self.generation_policy_service = generation_policy_service
        self.llm_service = llm_service
        self.session = session

    async def resolve_prefetch_context(
        self,
        *,
        config: Any,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: str,
        chapter_mission: Optional[dict],
        prefetch_tasks: Any,
        pre_rag_context: Optional[Dict[str, Any]],
        pre_rag_stats: Optional[Dict[str, Any]],
        history_context: Dict[str, Any],
        telemetry: Any,
    ) -> ResolvedPrefetchContext:
        enhanced_context: Dict[str, Any] = {}
        if getattr(prefetch_tasks, "enhanced_context_task", None) is not None:
            enhanced_result = await prefetch_tasks.enhanced_context_task
            if isinstance(enhanced_result, dict):
                enhanced_context = enhanced_result

        project_memory_text = await prefetch_tasks.memory_text_task

        # 注意: 历史上的 rag_mode="two_stage"（KnowledgeRetrievalService 第二套检索）已移除，
        # 现统一走单一的多查询向量 RAG（ChapterContextService）。为不破坏 API 契约，
        # 仍接受 rag_mode="two_stage" 入参，但行为等价于 simple，优雅回退。
        rag_context: Optional[Dict[str, Any]] = None
        knowledge_context: Optional[str] = None
        rag_stats: Optional[Dict[str, Any]] = None
        if config.enable_rag:
            if pre_rag_context:
                rag_context = pre_rag_context
                rag_stats = {
                    **(pre_rag_stats or {}),
                    "mode": "simple",
                    "reused": True,
                    "chunks": len(rag_context.get("chunks", [])) if rag_context else 0,
                    "summaries": len(rag_context.get("summaries", [])) if rag_context else 0,
                }
            elif getattr(prefetch_tasks, "rag_task", None) is not None:
                routed_local = await prefetch_tasks.rag_task
                rag_context = {
                    "chunks": list((routed_local or {}).get("chunks") or []),
                    "summaries": list((routed_local or {}).get("summaries") or []),
                }
                rag_stats = {
                    "mode": "simple",
                    **dict((routed_local or {}).get("stats") or {}),
                    "chunks": len(rag_context.get("chunks", [])) if rag_context else 0,
                    "summaries": len(rag_context.get("summaries", [])) if rag_context else 0,
                    "queries": list((routed_local or {}).get("queries") or []),
                }

        if rag_context or knowledge_context:
            await telemetry.emit_rag(
                {
                    "chunks": rag_context.get("chunks", []) if rag_context else [],
                    "summaries": rag_context.get("summaries", []) if rag_context else [],
                    "stats": rag_stats or {},
                }
            )

        writer_prompt = await prefetch_tasks.writer_prompt_task
        if not writer_prompt:
            raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置")

        return ResolvedPrefetchContext(
            enhanced_context=enhanced_context,
            project_memory_text=project_memory_text,
            rag_context=rag_context,
            knowledge_context=knowledge_context,
            rag_stats=rag_stats,
            writer_prompt=writer_prompt,
        )
