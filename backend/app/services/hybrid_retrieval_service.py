# AIMETA P=混合检索融合服务_Vector+BM25+RRF|R=混合检索_RRF融合|NR=不含索引构建_不含Rerank|E=HybridRetrievalService|X=internal|A=混合检索|D=vector_store_bm25_index|S=net|RD=./README.ai
"""
混合检索融合服务 (HybridRetrievalService)

实现：
1. Vector + BM25 双路检索
2. RRF (Reciprocal Rank Fusion) 融合排名
3. BM25-only 结果自动补充内容（从 Qdrant 回查）
4. 回溯搜索：scene chunk → 加载 parent summary

Rerank 由上层调用方统一控制，本服务不自行调用 Reranker。
"""
import logging
from typing import Any, Dict, List, Optional, Sequence

from ..core.config import settings
from .bm25_index_service import BM25IndexService
from .vector_store_service import RetrievedChunk, RetrievedSummary, VectorStoreService

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """混合检索融合服务：向量 + BM25 → RRF。"""

    RRF_K = 60

    def __init__(
        self,
        vector_store: VectorStoreService,
        bm25_service: Optional[BM25IndexService] = None,
        llm_service: Optional[Any] = None,
    ) -> None:
        self._vector_store = vector_store
        self._bm25_service = bm25_service or BM25IndexService()
        self._llm_service = llm_service

    async def hybrid_search(
        self,
        *,
        project_id: str,
        query_text: str,
        query_embedding: Sequence[float],
        top_k: int = 10,
        bm25_weight: Optional[float] = None,
        user_id: Optional[int] = None,
        # 保留签名兼容，但忽略；rerank 由上层统一控制
        enable_rerank: Optional[bool] = None,
    ) -> Dict[str, List[Any]]:
        """执行混合检索：向量 + BM25 → RRF 融合。

        不自行 rerank；上层应在拿到结果后按需调用 rerank_utils。
        """
        _ = user_id
        bm25_w = bm25_weight if bm25_weight is not None else getattr(settings, "rag_bm25_weight", 0.4)
        vector_w = 1.0 - bm25_w

        # 1. 向量检索
        vector_results = await self._vector_store.query_chunks(
            project_id=project_id,
            embedding=query_embedding,
            top_k=top_k * 2,
        )

        # 2. BM25 检索
        bm25_results = await self._bm25_service.search(
            project_id=project_id,
            query=query_text,
            top_k=top_k * 2,
        )

        # 3. RRF 融合（保留 BM25-only 条目，标记待补充）
        fused = self._rrf_fuse(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=vector_w,
            bm25_weight=bm25_w,
        )

        # 4. 为 BM25-only 结果补充内容
        fused = await self._fill_bm25_only_content(fused)

        # 5. 过滤无内容条目，按分数排序截断
        fused = [r for r in fused if r.get("content")]
        fused.sort(key=lambda x: x["score"], reverse=True)
        fused = fused[:top_k]

        # 6. 回溯搜索：加载 parent summary
        fused = await self._backtrack_summaries(project_id, query_embedding, fused)

        chunks = [self._to_retrieved_chunk(item) for item in fused]
        try:
            summaries: List[RetrievedSummary] = await self._vector_store.query_summaries(
                project_id=project_id,
                embedding=query_embedding,
                top_k=min(top_k, getattr(settings, "vector_top_k_summaries", 3)),
            )
        except Exception as exc:
            logger.warning("混合检索摘要回溯失败，返回空摘要列表: %s", exc)
            summaries = []

        return {
            "chunks": chunks,
            "summaries": summaries,
        }

    # ------------------------------------------------------------------
    # RRF 融合
    # ------------------------------------------------------------------

    def _rrf_fuse(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[Dict[str, Any]],
        vector_weight: float,
        bm25_weight: float,
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion 融合排名，BM25-only 结果也保留。"""
        scores: Dict[str, Dict[str, Any]] = {}

        # 按 chunk_id 建立向量结果索引，加速 BM25 合并
        vector_by_chunk_id: Dict[str, str] = {}
        for rank, chunk in enumerate(vector_results):
            key = f"v_{chunk.chapter_number}_{hash(chunk.content[:100])}"
            rrf_score = vector_weight * self._rrf_score(rank)
            chunk_id = (chunk.metadata or {}).get("chunk_id", "")
            scores[key] = {
                "content": chunk.content,
                "chapter_number": chunk.chapter_number,
                "chapter_title": chunk.chapter_title,
                "score": rrf_score,
                "metadata": chunk.metadata,
                "sources": ["vector"],
                "vector_rank": rank,
            }
            if chunk_id:
                vector_by_chunk_id[chunk_id] = key

        for rank, item in enumerate(bm25_results):
            chunk_id = item.get("chunk_id", "")
            fuse_key = vector_by_chunk_id.get(chunk_id)
            if fuse_key and fuse_key in scores:
                scores[fuse_key]["score"] += bm25_weight * self._rrf_score(rank)
                scores[fuse_key]["sources"].append("bm25")
                scores[fuse_key]["bm25_rank"] = rank
            else:
                key = f"b_{chunk_id}_{rank}"
                scores[key] = {
                    "chunk_id": chunk_id,
                    "content": "",
                    "chapter_number": 0,
                    "score": bm25_weight * self._rrf_score(rank),
                    "sources": ["bm25"],
                    "bm25_rank": rank,
                    "bm25_score": item.get("bm25_score", 0),
                    "_needs_content": True,
                }

        return sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    def _rrf_score(self, rank: int) -> float:
        return 1.0 / (self.RRF_K + rank)

    # ------------------------------------------------------------------
    # BM25-only 内容回填
    # ------------------------------------------------------------------

    async def _fill_bm25_only_content(
        self, fused: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从 Qdrant 补充 BM25-only 结果的 content。"""
        missing_ids = [
            r["chunk_id"] for r in fused
            if r.get("_needs_content") and r.get("chunk_id")
        ]
        if not missing_ids:
            return fused

        chunk_map = await self._vector_store.retrieve_chunks_by_ids(chunk_ids=missing_ids)
        filled = 0
        for r in fused:
            if r.get("_needs_content") and r.get("chunk_id"):
                found = chunk_map.get(r["chunk_id"])
                if found:
                    r["content"] = found.content
                    r["chapter_number"] = found.chapter_number
                    r["chapter_title"] = found.chapter_title
                    r["metadata"] = found.metadata
                    filled += 1
                r.pop("_needs_content", None)

        if filled:
            logger.info("BM25-only 内容回填: %d/%d 条", filled, len(missing_ids))
        return fused

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _to_retrieved_chunk(self, item: Dict[str, Any]) -> RetrievedChunk:
        base_metadata = item.get("metadata")
        metadata = dict(base_metadata) if isinstance(base_metadata, dict) else {}
        if item.get("sources"):
            metadata.setdefault("retrieval_sources", item.get("sources"))
        if item.get("parent_summary"):
            metadata.setdefault("parent_summary", item.get("parent_summary"))
        if item.get("chunk_id"):
            metadata.setdefault("chunk_id", item.get("chunk_id"))

        return RetrievedChunk(
            content=item.get("content", ""),
            chapter_number=int(item.get("chapter_number") or 0),
            chapter_title=item.get("chapter_title"),
            score=float(item.get("score", 0.0)),
            metadata=metadata,
        )

    async def _backtrack_summaries(
        self,
        project_id: str,
        query_embedding: Sequence[float],
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """回溯搜索：为检索到的 chunk 加载所属章节的 summary。"""
        if not results:
            return results

        chapter_numbers = {r.get("chapter_number") for r in results if r.get("chapter_number")}
        if not chapter_numbers:
            return results

        summaries = await self._vector_store.query_summaries(
            project_id=project_id,
            embedding=query_embedding,
            top_k=len(chapter_numbers),
        )

        summary_map = {s.chapter_number: s.summary for s in summaries}

        for result in results:
            ch_num = result.get("chapter_number")
            if ch_num and ch_num in summary_map:
                result["parent_summary"] = summary_map[ch_num]

        return results
