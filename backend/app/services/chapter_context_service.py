# AIMETA P=章节上下文服务_章节关联信息|R=上下文获取_关联分析|NR=不含内容生成|E=ChapterContextService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

"""
章节上下文组装服务：负责调用向量库检索上下文，并对结果做基础格式化。

所有关键步骤均包含中文注释，方便团队理解 RAG 流程。
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence

from ..core.config import settings
from ..services.llm_service import LLMService
from .vector_store_service import RetrievedChunk, RetrievedSummary, VectorStoreService
from .retrieval_scope import RetrievalScope, build_retrieval_scope
from .embedding_index_config import resolve_embedding_identity

logger = logging.getLogger(__name__)


@dataclass
class ChapterRAGContext:
    """封装检索得到的上下文结果。"""

    query: str
    chunks: List[RetrievedChunk]
    summaries: List[RetrievedSummary]
    receipt: Dict[str, Any] = field(default_factory=dict)

    def chunk_texts(self) -> List[str]:
        """将检索到的 chunk 转换成带序号的 Markdown 段落。"""
        lines = []
        _ordered_chunks = sorted(self.chunks, key=lambda c: (c.chapter_number, (c.metadata or {}).get("chunk_index", 0) if isinstance(c.metadata, dict) else 0))
        for idx, chunk in enumerate(_ordered_chunks, start=1):
            title = chunk.chapter_title or f"第{chunk.chapter_number}章"
            lines.append(
                f"### Chunk {idx}(来源：{title})\n{chunk.content.strip()}"
            )
        return lines

    def summary_lines(self) -> List[str]:
        """整理章节摘要，方便直接插入 Prompt。"""
        lines = []
        for summary in sorted(self.summaries, key=lambda s: s.chapter_number):
            lines.append(
                f"- 第{summary.chapter_number}章 - {summary.title}:{summary.summary.strip()}"
            )
        return lines


    def to_payload(self) -> Dict[str, Any]:
        return {"chunks": self.chunk_texts(), "summaries": self.summary_lines(),
                "chunk_records": [asdict(chunk) for chunk in self.chunks],
                "summary_records": [asdict(summary) for summary in self.summaries],
                "context_receipt": dict(self.receipt)}


def validate_rag_payload(payload: Dict[str, Any], scope: RetrievalScope) -> Dict[str, Any]:
    """Revalidate prefetched evidence at the final consumer; never trust old strings."""
    chunks = [RetrievedChunk(**{key: item[key] for key in
              ("content", "chapter_number", "chapter_title", "score", "metadata", "score_kind")
              if key in item})
              for item in payload.get("chunk_records", []) if isinstance(item, dict)
              and scope.accepts(item.get("chapter_number"), item.get("metadata"))]
    summaries = [RetrievedSummary(**{key: item[key] for key in
                 ("chapter_number", "title", "summary", "score", "metadata", "score_kind")
                 if key in item})
                 for item in payload.get("summary_records", []) if isinstance(item, dict)
                 and (scope.accepts_aggregate(item.get("metadata"))
                      if (item.get("metadata") or {}).get("contributing_sources")
                      else scope.accepts(item.get("chapter_number"), item.get("metadata")))]
    receipt = dict(payload.get("context_receipt") or {})
    receipt.update(revalidated=True, injected=len(chunks), summaries=len(summaries))
    return ChapterRAGContext("", chunks, summaries, receipt).to_payload()


class ChapterContextService:
    """章节上下文服务，整合查询、格式化与容错逻辑。"""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        vector_store: Optional[VectorStoreService] = None,
    ) -> None:
        self._llm_service = llm_service
        self._vector_store = vector_store

    async def retrieve_for_generation(
        self, *, project_id: str, query_text: str, user_id: int,
        top_k_chunks: Optional[int] = None, top_k_summaries: Optional[int] = None,
        retrieval_mode: str = "vector", scope: Optional[RetrievalScope] = None,
        before_chapter: Optional[int] = None,
    ) -> ChapterRAGContext:
        """The single-query path shares the same filtering and receipt contract."""
        return await self.retrieve_multi_query(
            project_id=project_id, queries=[query_text], user_id=user_id,
            top_k_chunks=top_k_chunks, top_k_summaries=top_k_summaries,
            retrieval_mode=retrieval_mode, scope=scope, before_chapter=before_chapter,
        )

    async def retrieve_multi_query(
        self, *, project_id: str, queries: List[str], user_id: int,
        top_k_chunks: Optional[int] = None, top_k_summaries: Optional[int] = None,
        retrieval_mode: str = "vector", min_score: Optional[float] = None,
        scope: Optional[RetrievalScope] = None, before_chapter: Optional[int] = None,
    ) -> ChapterRAGContext:
        """Retrieve factual evidence, never compare RRF/rerank scores with cosine."""
        normalized = [self._normalize(q) for q in queries if q and q.strip()]
        query = normalized[0] if normalized else ""
        receipt: Dict[str, Any] = {"status": "skipped", "mode": retrieval_mode,
                                  "raw": 0, "deduped": 0, "threshold_filtered": 0,
                                  "provenance_filtered": 0, "injected": 0}
        empty = ChapterRAGContext(query, [], [], receipt)
        if not normalized or not settings.vector_store_enabled or not self._vector_store:
            receipt["reason"] = "empty_queries_or_store_unavailable"
            return empty
        if scope is None and before_chapter is not None:
            try:
                scope = await build_retrieval_scope(project_id=project_id, before_chapter=before_chapter)
            except Exception:
                logger.exception("Unable to construct factual retrieval scope: project=%s", project_id)
                receipt["reason"] = "scope_unavailable"
                return empty
        if scope is None or scope.project_id != project_id:
            receipt["reason"] = "missing_retrieval_scope"
            return empty
        receipt["before_chapter"] = scope.before_chapter
        if min_score is None:
            min_score = getattr(settings, "rag_min_score", 0.35)
        top_k = top_k_chunks or settings.vector_top_k_chunks
        from ..utils.rerank_utils import is_rerank_enabled, rerank_documents
        need_rerank = await is_rerank_enabled()
        identity = await resolve_embedding_identity(self._llm_service, user_id=user_id)
        embeddings = await self._llm_service.get_embeddings_batch(normalized, user_id=user_id)
        if identity != await resolve_embedding_identity(self._llm_service, user_id=user_id):
            receipt["reason"] = "embedding_configuration_changed_during_query"
            return empty
        dimensions = {len(embedding) for embedding in embeddings if embedding}
        if len(dimensions) > 1:
            receipt["reason"] = "inconsistent_embedding_dimensions"
            return empty
        configure = getattr(self._vector_store, "configure_embedding", None)
        if dimensions and configure is not None:
            fingerprint = await configure(dimension=next(iter(dimensions)), identity=identity)
            receipt["embedding_fingerprint"] = fingerprint

        async def search_one(text: str, embedding: Sequence[float]) -> List[RetrievedChunk]:
            if retrieval_mode == "hybrid":
                try:
                    from .hybrid_retrieval_service import HybridRetrievalService
                    result = await HybridRetrievalService(self._vector_store).hybrid_search(
                        project_id=project_id, query_text=text, query_embedding=embedding,
                        top_k=top_k, user_id=user_id, scope=scope,
                    )
                    chunks = result.get("chunks", [])
                    # Defend the merge boundary even against legacy hybrid adapters.
                    if all(getattr(chunk, "score_kind", "cosine") == "rrf" for chunk in chunks):
                        return chunks
                    return self._as_rank_scores(chunks)
                except Exception as exc:
                    logger.warning("Hybrid query degraded to vector ranking: %s", exc)
                    receipt["degraded"] = True
            chunks = await self._vector_store.query_chunks(
                project_id=project_id, embedding=embedding, top_k=top_k, scope=scope,
            )
            if retrieval_mode == "hybrid":
                return self._as_rank_scores(chunks)
            return chunks

        results = await asyncio.gather(*(
            search_one(text, embedding) for text, embedding in zip(normalized, embeddings) if embedding
        ))
        merged: Dict[str, RetrievedChunk] = {}
        for chunks in results:
            receipt["raw"] += len(chunks)
            for chunk in chunks:
                metadata = chunk.metadata if isinstance(chunk.metadata, dict) else {}
                if not scope.accepts(chunk.chapter_number, metadata):
                    receipt["provenance_filtered"] += 1
                    continue
                if chunk.score_kind == "cosine" and min_score > 0 and chunk.score < min_score:
                    receipt["threshold_filtered"] += 1
                    continue
                key = metadata.get("chunk_id") or f"{chunk.chapter_number}:{chunk.content}"
                if key not in merged or chunk.score > merged[key].score:
                    merged[key] = chunk
        receipt["deduped"] = len(merged)
        ordered = sorted(merged.values(), key=lambda chunk: chunk.score, reverse=True)
        chunks = ordered[:top_k * 2 if need_rerank else top_k]
        if need_rerank and chunks:
            try:
                scored = await rerank_documents(
                    " ".join(normalized[:2]), [chunk.content for chunk in chunks],
                    original_scores=[chunk.score for chunk in chunks], top_n=len(chunks),
                )
                if scored:
                    reranked = [replace(chunks[item["index"]], score=item["combined_score"],
                                        score_kind="rerank", metadata={**chunks[item["index"]].metadata,
                                            "original_score": chunks[item["index"]].score,
                                            "original_score_kind": chunks[item["index"]].score_kind})
                                for item in scored if 0 <= item["index"] < len(chunks)]
                    if reranked:
                        chunks = reranked
                        receipt["reranked"] = True
            except Exception as exc:
                logger.warning("Rerank failed, retaining retrieval order: %s", exc)
                receipt["rerank_status"] = "failed"
        chunks = chunks[:top_k]
        first_embedding = next((embedding for embedding in embeddings if embedding), None)
        summaries = []
        if first_embedding:
            summaries = await self._vector_store.query_summaries(
                project_id=project_id, embedding=first_embedding,
                top_k=top_k_summaries, scope=scope,
            )
            summaries = [summary for summary in summaries
                         if (scope.accepts_aggregate(summary.metadata)
                             if summary.metadata.get("contributing_sources")
                             else scope.accepts(summary.chapter_number, summary.metadata))]
        receipt.update(status="completed", injected=len(chunks), summaries=len(summaries),
                       budget_trimmed=max(0, len(ordered) - len(chunks)))
        logger.info("RAG retrieval receipt: project=%s receipt=%s", project_id, receipt)
        return ChapterRAGContext(query, chunks, summaries, receipt)

    @staticmethod
    def _as_rank_scores(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        return [replace(chunk, score=1.0 / (60 + rank), score_kind="rrf",
                        metadata={**(chunk.metadata or {}), "vector_rank": rank,
                                  "vector_score": chunk.score, "retrieval_sources": ["vector"],
                                  "degraded": "vector_only"})
                for rank, chunk in enumerate(chunks)]

    @staticmethod
    def _normalize(text: str) -> str:
        """统一压缩空白字符，避免影响检索效果。"""
        return " ".join(text.split())


__all__ = [
    "ChapterContextService",
    "ChapterRAGContext",
]
