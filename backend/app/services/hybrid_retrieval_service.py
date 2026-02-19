# AIMETA P=混合检索融合服务_Vector+BM25+RRF|R=混合检索_RRF融合_可选Rerank|NR=不含索引构建|E=HybridRetrievalService|X=internal|A=混合检索|D=vector_store_bm25_index|S=net|RD=./README.ai
"""
混合检索融合服务 (HybridRetrievalService)

实现：
1. Vector + BM25 双路检索
2. RRF (Reciprocal Rank Fusion) 融合排名
3. 可选 Rerank API 调用（Jina AI 等）
4. 回溯搜索：scene chunk → 加载 parent summary
"""
import logging
from typing import Any, Dict, List, Optional, Sequence

import httpx

from ..core.config import settings
from .bm25_index_service import BM25IndexService
from .vector_store_service import RetrievedChunk, VectorStoreService

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """混合检索融合服务：向量 + BM25 → RRF → 可选 Rerank。"""

    RRF_K = 60  # RRF 常量

    def __init__(
        self,
        vector_store: VectorStoreService,
        bm25_service: BM25IndexService,
    ) -> None:
        self._vector_store = vector_store
        self._bm25_service = bm25_service

    async def hybrid_search(
        self,
        *,
        project_id: str,
        query_text: str,
        query_embedding: Sequence[float],
        top_k: int = 10,
        bm25_weight: Optional[float] = None,
        enable_rerank: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行混合检索：向量 + BM25 → RRF 融合 → 可选 Rerank。

        Returns:
            排序后的结果列表，每项包含 chunk_id, content, score, source 等信息。
        """
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

        # 3. RRF 融合
        fused = self._rrf_fuse(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=vector_w,
            bm25_weight=bm25_w,
        )

        # 取 top_k
        fused = fused[:top_k]

        # 4. 可选 Rerank
        should_rerank = enable_rerank if enable_rerank is not None else getattr(settings, "rag_reranker_enabled", False)
        if should_rerank and fused:
            fused = await self._rerank(query_text, fused)

        # 5. 回溯搜索：加载 parent summary
        fused = await self._backtrack_summaries(project_id, query_embedding, fused)

        return fused

    def _rrf_fuse(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[Dict[str, Any]],
        vector_weight: float,
        bm25_weight: float,
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion 融合排名。"""
        scores: Dict[str, Dict[str, Any]] = {}

        # 向量结果排名（已按 distance ASC 排序）
        for rank, chunk in enumerate(vector_results):
            key = f"v_{chunk.chapter_number}_{hash(chunk.content[:100])}"
            rrf_score = vector_weight * self._rrf_score(rank)
            scores[key] = {
                "content": chunk.content,
                "chapter_number": chunk.chapter_number,
                "chapter_title": chunk.chapter_title,
                "score": rrf_score,
                "metadata": chunk.metadata,
                "sources": ["vector"],
                "vector_rank": rank,
            }

        # BM25 结果排名（已按 score DESC 排序）
        for rank, item in enumerate(bm25_results):
            chunk_id = item.get("chunk_id", "")
            # 尝试找到已有的向量结果进行合并
            merged = False
            for key, existing in scores.items():
                if chunk_id and existing.get("metadata", {}).get("chunk_id") == chunk_id:
                    existing["score"] += bm25_weight * self._rrf_score(rank)
                    existing["sources"].append("bm25")
                    existing["bm25_rank"] = rank
                    merged = True
                    break

            if not merged:
                key = f"b_{chunk_id}_{rank}"
                scores[key] = {
                    "chunk_id": chunk_id,
                    "content": "",
                    "chapter_number": 0,
                    "score": bm25_weight * self._rrf_score(rank),
                    "sources": ["bm25"],
                    "bm25_rank": rank,
                    "bm25_score": item.get("bm25_score", 0),
                }

        # 按融合分数排序
        sorted_results = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        # 过滤掉没有内容的纯 BM25 结果（需要从向量库补充内容）
        return [r for r in sorted_results if r.get("content")]

    def _rrf_score(self, rank: int) -> float:
        """计算 RRF 分数。"""
        return 1.0 / (self.RRF_K + rank)

    async def _rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """调用外部 Reranker API 重排序。"""
        api_url = getattr(settings, "rag_reranker_api_url", None)
        api_key = getattr(settings, "rag_reranker_api_key", None)
        model = getattr(settings, "rag_reranker_model", "jina-reranker-v2-base-multilingual")

        if not api_url or not api_key:
            return results

        documents = [r.get("content", "")[:500] for r in results]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    str(api_url),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "query": query,
                        "documents": documents,
                        "top_n": len(documents),
                    },
                )
                response.raise_for_status()
                data = response.json()

            reranked_results = data.get("results", [])
            reranked = []
            for item in sorted(reranked_results, key=lambda x: x.get("relevance_score", 0), reverse=True):
                idx = item.get("index", 0)
                if idx < len(results):
                    entry = results[idx].copy()
                    entry["rerank_score"] = item.get("relevance_score", 0)
                    entry["score"] = item.get("relevance_score", entry["score"])
                    reranked.append(entry)

            logger.info("Rerank 完成: %d → %d 结果", len(results), len(reranked))
            return reranked if reranked else results

        except Exception as exc:
            logger.warning("Rerank API 调用失败，保持原排序: %s", exc)
            return results

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

        # 从 rag_summaries 获取相关章节的摘要
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
