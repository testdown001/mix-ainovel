# AIMETA P=章节上下文服务_章节关联信息|R=上下文获取_关联分析|NR=不含内容生成|E=ChapterContextService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

"""
章节上下文组装服务：负责调用向量库检索上下文，并对结果做基础格式化。

所有关键步骤均包含中文注释，方便团队理解 RAG 流程。
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ..core.config import settings
from ..services.llm_service import LLMService
from .vector_store_service import RetrievedChunk, RetrievedSummary, VectorStoreService

logger = logging.getLogger(__name__)


@dataclass
class ChapterRAGContext:
    """封装检索得到的上下文结果。"""

    query: str
    chunks: List[RetrievedChunk]
    summaries: List[RetrievedSummary]

    def chunk_texts(self) -> List[str]:
        """将检索到的 chunk 转换成带序号的 Markdown 段落。"""
        lines = []
        for idx, chunk in enumerate(self.chunks, start=1):
            title = chunk.chapter_title or f"第{chunk.chapter_number}章"
            lines.append(
                f"### Chunk {idx}(来源：{title})\n{chunk.content.strip()}"
            )
        return lines

    def summary_lines(self) -> List[str]:
        """整理章节摘要，方便直接插入 Prompt。"""
        lines = []
        for summary in self.summaries:
            lines.append(
                f"- 第{summary.chapter_number}章 - {summary.title}:{summary.summary.strip()}"
            )
        return lines


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
        self,
        *,
        project_id: str,
        query_text: str,
        user_id: int,
        top_k_chunks: Optional[int] = None,
        top_k_summaries: Optional[int] = None,
        retrieval_mode: str = "vector",
    ) -> ChapterRAGContext:
        """根据章节摘要构造检索向量，并返回 RAG 上下文。"""
        query = self._normalize(query_text)
        if not settings.vector_store_enabled or not self._vector_store:
            logger.error("向量库未启用或初始化失败，跳过检索: project=%s", project_id)
            return ChapterRAGContext(query=query, chunks=[], summaries=[])

        # get_embedding 会自动根据配置选择正确的模型
        embedding = await self._llm_service.get_embedding(query, user_id=user_id)
        if not embedding:
            logger.warning("检索查询向量生成失败: project=%s chapter_query=%s", project_id, query)
            return ChapterRAGContext(query=query, chunks=[], summaries=[])

        from ..utils.rerank_utils import is_rerank_enabled, rerank_documents
        need_rerank = is_rerank_enabled()

        # 混合检索模式
        if retrieval_mode == "hybrid":
            try:
                from .hybrid_retrieval_service import HybridRetrievalService
                effective_top_k_hybrid = top_k_chunks or settings.vector_top_k_chunks
                hybrid = HybridRetrievalService(
                    vector_store=self._vector_store,
                    llm_service=self._llm_service,
                )
                hybrid_results = await hybrid.hybrid_search(
                    project_id=project_id,
                    query_text=query,
                    query_embedding=embedding,
                    top_k=effective_top_k_hybrid * 2 if need_rerank else effective_top_k_hybrid,
                    user_id=user_id,
                )
                chunks = hybrid_results.get("chunks", [])
                summaries = hybrid_results.get("summaries", [])

                if need_rerank and chunks:
                    docs = [c.content for c in chunks]
                    orig = [c.score for c in chunks]
                    scored = await rerank_documents(query, docs, original_scores=orig, top_n=len(docs))
                    if scored:
                        reranked = []
                        for item in scored:
                            idx = item["index"]
                            if idx < len(chunks):
                                chunks[idx] = RetrievedChunk(
                                    content=chunks[idx].content,
                                    chapter_number=chunks[idx].chapter_number,
                                    chapter_title=chunks[idx].chapter_title,
                                    score=item["combined_score"],
                                    metadata=chunks[idx].metadata,
                                )
                                reranked.append(chunks[idx])
                        chunks = reranked[:effective_top_k_hybrid]

                logger.info(
                    "混合检索完成: project=%s chunks=%d summaries=%d reranked=%s",
                    project_id, len(chunks), len(summaries), need_rerank,
                )
                return ChapterRAGContext(query=query, chunks=chunks, summaries=summaries)
            except Exception as exc:
                logger.warning("混合检索失败，回退到纯向量检索: %s", exc)

        effective_top_k = top_k_chunks or settings.vector_top_k_chunks

        chunks = await self._vector_store.query_chunks(
            project_id=project_id,
            embedding=embedding,
            top_k=effective_top_k * 2 if need_rerank else effective_top_k,
        )

        if need_rerank and chunks:
            documents = [c.content for c in chunks]
            original_scores = [c.score for c in chunks]
            scored = await rerank_documents(
                query, documents, original_scores=original_scores, top_n=len(documents),
            )
            if scored:
                reranked = []
                for item in scored:
                    idx = item["index"]
                    if idx < len(chunks):
                        chunks[idx] = RetrievedChunk(
                            content=chunks[idx].content,
                            chapter_number=chunks[idx].chapter_number,
                            chapter_title=chunks[idx].chapter_title,
                            score=item["combined_score"],
                            metadata=chunks[idx].metadata,
                        )
                        reranked.append(chunks[idx])
                chunks = reranked[:effective_top_k]

        summaries = await self._vector_store.query_summaries(
            project_id=project_id,
            embedding=embedding,
            top_k=top_k_summaries,
        )
        logger.info(
            "章节上下文检索完成: project=%s chunks=%d summaries=%d reranked=%s query_preview=%s",
            project_id,
            len(chunks),
            len(summaries),
            need_rerank,
            query[:80],
        )
        return ChapterRAGContext(query=query, chunks=chunks, summaries=summaries)

    async def retrieve_multi_query(
        self,
        *,
        project_id: str,
        queries: List[str],
        user_id: int,
        top_k_chunks: Optional[int] = None,
        top_k_summaries: Optional[int] = None,
        retrieval_mode: str = "vector",
        min_score: Optional[float] = None,
    ) -> ChapterRAGContext:
        """多查询检索：每个 query 独立 embedding+检索，合并去重后返回。

        相比单查询，多查询可避免长文本向量被稀释的问题，
        每个聚焦查询独立匹配，命中率更高。
        """
        if not queries:
            return ChapterRAGContext(query="", chunks=[], summaries=[])

        if not settings.vector_store_enabled or not self._vector_store:
            logger.error("向量库未启用或初始化失败，跳过检索: project=%s", project_id)
            return ChapterRAGContext(query=queries[0], chunks=[], summaries=[])

        if min_score is None:
            min_score = getattr(settings, "rag_min_score", 0.35)

        effective_top_k = top_k_chunks or settings.vector_top_k_chunks

        from ..utils.rerank_utils import is_rerank_enabled, rerank_documents
        need_rerank = is_rerank_enabled()
        per_query_k = effective_top_k  # 每个 query 取 top_k 条

        # ---- 并行生成所有 query 的 embedding ----
        normalized = [self._normalize(q) for q in queries if q and q.strip()]
        if not normalized:
            return ChapterRAGContext(query="", chunks=[], summaries=[])

        embeddings: List[Optional[Sequence[float]]] = await asyncio.gather(
            *[self._llm_service.get_embedding(q, user_id=user_id) for q in normalized]
        )

        # ---- 并行检索每个 query ----
        async def _search_single(query_text: str, emb: Sequence[float]) -> List[RetrievedChunk]:
            if retrieval_mode == "hybrid":
                try:
                    from .hybrid_retrieval_service import HybridRetrievalService
                    hybrid = HybridRetrievalService(
                        vector_store=self._vector_store,
                        llm_service=self._llm_service,
                    )
                    result = await hybrid.hybrid_search(
                        project_id=project_id,
                        query_text=query_text,
                        query_embedding=emb,
                        top_k=per_query_k,
                        user_id=user_id,
                    )
                    return result.get("chunks", [])
                except Exception:
                    pass  # 回退到纯向量

            return await self._vector_store.query_chunks(
                project_id=project_id,
                embedding=emb,
                top_k=per_query_k,
            )

        search_tasks = []
        valid_queries = []
        for q, emb in zip(normalized, embeddings):
            if emb:
                search_tasks.append(_search_single(q, emb))
                valid_queries.append(q)

        if not search_tasks:
            logger.warning("多查询RAG: 所有 embedding 生成失败 project=%s", project_id)
            return ChapterRAGContext(query=normalized[0], chunks=[], summaries=[])

        all_chunk_results: List[List[RetrievedChunk]] = await asyncio.gather(*search_tasks)

        # ---- 合并去重：按 chunk_id 保留最高分 ----
        merged: Dict[str, RetrievedChunk] = {}
        total_raw = 0
        for chunk_list in all_chunk_results:
            total_raw += len(chunk_list)
            for chunk in chunk_list:
                cid = chunk.metadata.get("chunk_id", f"{chunk.chapter_number}:{chunk.content[:50]}")
                if cid not in merged or chunk.score > merged[cid].score:
                    merged[cid] = chunk

        deduped = list(merged.values())
        deduped_count = len(deduped)

        # ---- 分数门槛过滤 ----
        if min_score > 0:
            deduped = [c for c in deduped if c.score >= min_score]
        filtered_count = len(deduped)

        # ---- 排序 + 截断 ----
        deduped.sort(key=lambda c: c.score, reverse=True)
        final_chunks = deduped[:effective_top_k * 2 if need_rerank else effective_top_k]

        # ---- Rerank（合并后统一重排） ----
        if need_rerank and final_chunks:
            combined_query = " ".join(valid_queries[:2])  # 用前两个 query 做 rerank
            docs = [c.content for c in final_chunks]
            orig_scores = [c.score for c in final_chunks]
            scored = await rerank_documents(
                combined_query, docs, original_scores=orig_scores, top_n=len(docs),
            )
            if scored:
                reranked = []
                for item in scored:
                    idx = item["index"]
                    if idx < len(final_chunks):
                        final_chunks[idx] = RetrievedChunk(
                            content=final_chunks[idx].content,
                            chapter_number=final_chunks[idx].chapter_number,
                            chapter_title=final_chunks[idx].chapter_title,
                            score=item["combined_score"],
                            metadata=final_chunks[idx].metadata,
                        )
                        reranked.append(final_chunks[idx])
                final_chunks = reranked[:effective_top_k]
            else:
                final_chunks = final_chunks[:effective_top_k]
        final_count = len(final_chunks)

        # ---- 摘要检索：用第一个有效 embedding ----
        summaries: List[RetrievedSummary] = []
        first_emb = next((e for e in embeddings if e), None)
        if first_emb:
            summaries = await self._vector_store.query_summaries(
                project_id=project_id,
                embedding=first_emb,
                top_k=top_k_summaries,
            )

        hit_chapters = sorted({c.chapter_number for c in final_chunks})
        logger.info(
            "多查询RAG检索完成: project=%s queries=%d raw=%d deduped=%d filtered=%d final=%d "
            "min_score=%.2f hit_chapters=%s reranked=%s",
            project_id, len(valid_queries), total_raw, deduped_count,
            filtered_count, final_count, min_score, hit_chapters, need_rerank,
        )

        return ChapterRAGContext(
            query=normalized[0],
            chunks=final_chunks,
            summaries=summaries,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """统一压缩空白字符，避免影响检索效果。"""
        return " ".join(text.split())


__all__ = [
    "ChapterContextService",
    "ChapterRAGContext",
]
