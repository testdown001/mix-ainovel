# AIMETA P=Rerank工具_统一重排序|R=外部Reranker_API调用_加权融合|NR=不含检索逻辑|E=rerank_documents|X=internal|A=工具函数|D=httpx|S=net|RD=./README.ai
"""
统一 Rerank 工具模块

提供单一入口调用外部 Reranker API，
并将 reranker 分数与原始分数加权组合，避免直接覆盖。

配置口径（2026-08-01 起，与全系统 LLM 通道一致）：
    SystemConfig 表 `rerank.*` 优先 → env（`settings.rag_reranker_*`）兜底。
env 只在首次启动时把值播种进 SystemConfig（见 db/system_config_defaults.py），
之后一切以后台「接口管理 → 重排序模型」为准，改完即时生效、无需重启。

仍保留 embedding 配置回退：未单独配置 `rerank.api_url/api_key` 时借用
`embedding.base_url`/`embedding.api_key` 并自动补 `/rerank`，以兼容旧部署。
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

RERANK_SCORE_WEIGHT = 0.6

# 连续失败达到该次数后，本进程内对该 URL 熄火，不再重试（与 llm_service 的
# 「按目标学习」进程级集合同一范式）。
# 动机：rerank.enabled 默认开而 api_url 可能缺省，此时会回退去猜
# embedding.base_url + "/rerank"。多数 embedding 供应商并不提供该端点，
# 于是每次检索都发一个注定失败的请求——降级虽优雅，但永久地白付一次往返和日志噪音。
# 注意：熄火是「进程级」的，多副本部署下后台测试只能解除当前进程的熄火，
# 其余副本要等各自的下一次成功调用或重启才恢复。
_RERANK_FAILURE_THRESHOLD = 3
_rerank_failures: Dict[str, int] = {}

# SystemConfig 键 → 缺省兜底值（取自 settings，即 env）
_CONFIG_FALLBACKS: Dict[str, Any] = {
    "rerank.enabled": lambda: settings.rag_reranker_enabled,
    "rerank.api_url": lambda: settings.rag_reranker_api_url,
    "rerank.api_key": lambda: settings.rag_reranker_api_key,
    "rerank.model": lambda: settings.rag_reranker_model,
    "embedding.base_url": lambda: settings.embedding_base_url,
    "embedding.api_key": lambda: settings.embedding_api_key,
}

_TRUTHY = {"1", "true", "yes", "on"}


async def _load_config() -> Dict[str, Optional[str]]:
    """一次查询取回 rerank 相关的全部配置项，DB 缺失的键回退到 env。

    刻意用「单次 IN 查询」而非逐键查询：本函数在每轮检索里会被调用两次
    （enabled 判定 + 地址解析），逐键查会把一次检索放大成 6 个 DB 往返。
    """
    keys = list(_CONFIG_FALLBACKS)
    values: Dict[str, Optional[str]] = {}
    try:
        from sqlalchemy import select

        from ..db.session import AsyncSessionLocal
        from ..models.system_config import SystemConfig

        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(SystemConfig.key, SystemConfig.value).where(SystemConfig.key.in_(keys))
            )
            for key, value in rows.all():
                if value not in (None, ""):
                    values[key] = value
    except Exception as exc:  # pragma: no cover - DB 不可用时静默回退 env
        logger.debug("读取 rerank 配置失败，回退环境变量: %s", exc)

    for key, fallback in _CONFIG_FALLBACKS.items():
        if values.get(key):
            continue
        raw = fallback()
        values[key] = str(raw) if raw not in (None, "") else None
    return values


def _as_bool(value: Optional[str]) -> bool:
    return str(value).strip().lower() in _TRUTHY if value is not None else False


def _to_rerank_endpoint(base_url: str) -> str:
    """基础地址自动补 `/rerank`；已是完整 rerank 端点则原样保留。"""
    url = str(base_url).rstrip("/")
    return url if url.endswith("/rerank") else url + "/rerank"


async def is_rerank_enabled() -> bool:
    """重排是否启用（后台开关优先，env 兜底）。"""
    config = await _load_config()
    return _as_bool(config.get("rerank.enabled"))


async def get_rerank_runtime_status() -> Dict[str, Any]:
    """返回当前实例的 Reranker 运行时状态，供启动日志、后台展示和诊断使用。"""
    config = await _load_config()
    model = config.get("rerank.model") or "jina-reranker-v2-base-multilingual"
    enabled = _as_bool(config.get("rerank.enabled"))

    dedicated_url = config.get("rerank.api_url")
    dedicated_key = config.get("rerank.api_key")
    if dedicated_url and dedicated_key:
        return {
            "enabled": enabled,
            "model": model,
            "config_source": "dedicated",
            "api_url": _to_rerank_endpoint(dedicated_url),
            "api_key_configured": True,
        }

    fallback_url = config.get("embedding.base_url")
    fallback_key = config.get("embedding.api_key")
    if fallback_url and fallback_key:
        return {
            "enabled": enabled,
            "model": model,
            "config_source": "embedding_fallback",
            "api_url": _to_rerank_endpoint(fallback_url),
            "api_key_configured": True,
        }

    return {
        "enabled": enabled,
        "model": model,
        "config_source": "unconfigured",
        "api_url": None,
        "api_key_configured": False,
    }


async def _resolve_rerank_config() -> Tuple[Optional[str], Optional[str], str]:
    """解析 rerank 的 API 地址、密钥和模型。

    优先级：专用 `rerank.api_url`/`rerank.api_key` → 旧兼容的 `embedding.*`。
    """
    config = await _load_config()
    model = config.get("rerank.model") or "jina-reranker-v2-base-multilingual"

    url = config.get("rerank.api_url")
    key = config.get("rerank.api_key")
    if not (url and key):
        url = config.get("embedding.base_url")
        key = config.get("embedding.api_key")
    if not (url and key):
        return None, None, model

    return _to_rerank_endpoint(url), key, model


def reset_rerank_failures(api_url: Optional[str] = None) -> None:
    """清除熄火计数。传 URL 只清该地址，否则全清（后台改配置/测试成功后调用）。"""
    if api_url:
        _rerank_failures.pop(api_url, None)
    else:
        _rerank_failures.clear()


async def _post_rerank(
    api_url: str,
    api_key: str,
    model: str,
    query: str,
    documents: List[str],
    top_n: int,
) -> Dict[str, Any]:
    """发一次 rerank 请求并返回解析后的 JSON（异常直接上抛，由调用方处理）。"""
    from .llm_tool import _get_ssl_verify

    async with httpx.AsyncClient(timeout=30.0, verify=_get_ssl_verify()) as client:
        response = await client.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            },
        )
        response.raise_for_status()
        return response.json()


async def test_rerank_connection() -> Dict[str, Any]:
    """真实发起一次最小 rerank 调用，检测配置可用性（后台「测试连接」按钮）。

    返回 ``{ok, model, latency_ms, detail}``，与 LLMService.test_channel 同构。
    任何异常都被捕获为 ok=False + detail，绝不抛出。
    成功时清除该地址的熄火计数——「管理员刚验证过」就是最可靠的恢复信号。
    """
    start = time.monotonic()
    status = await get_rerank_runtime_status()
    model = status["model"]
    api_url, api_key, _ = await _resolve_rerank_config()

    if not api_url or not api_key:
        return {
            "ok": False,
            "model": model,
            "latency_ms": 0,
            "detail": "未配置 Reranker 地址或 API Key（也无可回退的 embedding 配置）",
        }

    try:
        data = await _post_rerank(
            api_url,
            api_key,
            model,
            query="连接测试",
            documents=["这是一段用于连通性测试的文本。", "另一段无关文本。"],
            top_n=2,
        )
        latency = int((time.monotonic() - start) * 1000)
        results = data.get("results")
        if not results:
            return {
                "ok": False,
                "model": model,
                "latency_ms": latency,
                "detail": f"接口可达但未返回 results 字段，响应片段：{str(data)[:120]}",
            }
        reset_rerank_failures(api_url)
        source = "专用配置" if status["config_source"] == "dedicated" else "回退 embedding 配置"
        note = "" if status["enabled"] else "；⚠️ 当前开关为关闭状态，实际检索不会重排"
        return {
            "ok": True,
            "model": model,
            "latency_ms": latency,
            "detail": f"重排正常，返回 {len(results)} 条（{source}：{api_url}）{note}",
        }
    except Exception as exc:  # noqa: BLE001 - 测试不应抛出
        latency = int((time.monotonic() - start) * 1000)
        return {
            "ok": False,
            "model": model,
            "latency_ms": latency,
            "detail": f"{api_url} 调用失败：{str(exc)[:200]}",
        }


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
    if not documents:
        return None

    api_url, api_key, model = await _resolve_rerank_config()
    if not api_url or not api_key:
        logger.debug(
            "Rerank 配置不完整（未设置专用 Reranker 配置，且 embedding 配置也不可用），跳过重排"
        )
        return None

    if _rerank_failures.get(api_url, 0) >= _RERANK_FAILURE_THRESHOLD:
        logger.debug("Rerank 已因连续失败在本进程内熄火，跳过 (url=%s)", api_url)
        return None

    truncated = [d[:1024] for d in documents]

    try:
        data = await _post_rerank(
            api_url, api_key, model, query, truncated, top_n or len(truncated)
        )

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
        _rerank_failures.pop(api_url, None)  # 成功即清零，避免偶发抖动累积成熄火
        logger.info("Rerank 完成: %d 个文档已重排 (url=%s)", len(scored), api_url)
        return scored

    except Exception as exc:
        count = _rerank_failures.get(api_url, 0) + 1
        _rerank_failures[api_url] = count
        if count >= _RERANK_FAILURE_THRESHOLD:
            logger.warning(
                "Rerank API 连续失败 %d 次，本进程内不再重试该地址 (url=%s)；"
                "请到后台「接口管理 → 重排序模型」填写可用地址并点「测试连接」，"
                "或直接关闭该开关: %s",
                count, api_url, exc,
            )
        else:
            logger.warning(
                "Rerank API 调用失败，保持原排序 (url=%s, docs=%d): %s", api_url, len(documents), exc
            )
        return None
