# AIMETA P=Rerank工具_统一重排序|R=外部Reranker_API调用_加权融合|NR=不含检索逻辑|E=rerank_documents|X=internal|A=工具函数|D=httpx|S=net|RD=./README.ai
"""
统一 Rerank 工具模块

提供单一入口调用外部 Reranker API（Jina AI 等），
并将 reranker 分数与原始分数加权组合，避免直接覆盖。
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

RERANK_SCORE_WEIGHT = 0.6


def is_rerank_enabled() -> bool:
    """检查 reranker 是否已配置且启用。"""
    return bool(
        getattr(settings, "rag_reranker_enabled", False)
        and getattr(settings, "rag_reranker_api_url", None)
        and getattr(settings, "rag_reranker_api_key", None)
    )


async def rerank_documents(
    query: str,
    documents: List[str],
    *,
    original_scores: Optional[List[float]] = None,
    top_n: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """调用外部 Reranker API 并返回按加权组合分数排序的结果。

    Returns:
        按 combined_score 降序排列的列表
        ``[{"index": int, "relevance_score": float, "combined_score": float}, ...]``
        失败时返回 ``None``（调用方应保持原排序）。
    """
    api_url = getattr(settings, "rag_reranker_api_url", None)
    api_key = getattr(settings, "rag_reranker_api_key", None)
    model = getattr(settings, "rag_reranker_model", "jina-reranker-v2-base-multilingual")

    if not api_url or not api_key or not documents:
        return None

    truncated = [d[:800] for d in documents]

    try:
        from .llm_tool import _get_ssl_verify
        async with httpx.AsyncClient(timeout=30.0, verify=_get_ssl_verify()) as client:
            response = await client.post(
                str(api_url),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "query": query,
                    "documents": truncated,
                    "top_n": top_n or len(truncated),
                },
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        if not results:
            return None

        # 归一化原始分数到 [0, 1]（min-max）
        norm_originals: Optional[List[float]] = None
        if original_scores:
            max_s = max(original_scores) or 1.0
            min_s = min(original_scores)
            span = (max_s - min_s) or 1.0
            norm_originals = [(s - min_s) / span for s in original_scores]

        scored: List[Dict[str, Any]] = []
        for item in results:
            idx = item.get("index", 0)
            rerank_score = item.get("relevance_score", 0.0)

            if norm_originals and idx < len(norm_originals):
                w = RERANK_SCORE_WEIGHT
                combined = (1 - w) * norm_originals[idx] + w * rerank_score
            else:
                combined = rerank_score

            scored.append({
                "index": idx,
                "relevance_score": rerank_score,
                "combined_score": combined,
            })

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        logger.info("Rerank 完成: %d 个文档已重排", len(scored))
        return scored

    except Exception as exc:
        logger.warning("Rerank API 调用失败，保持原排序: %s", exc)
        return None
