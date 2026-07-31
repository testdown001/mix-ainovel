"""Reranker 连续失败熄火回归测试。

历史现象（2026-07-31 服务器实跑基线时观察到）：`rag_reranker_enabled` 默认 True 而
`rag_reranker_api_url` 默认 None，配置缺省时 rerank_utils 回退去猜
`embedding.base_url + "/rerank"`。生产 embedding 走的代理不提供该端点 → 每次检索都
发一个注定失败的 HTTP 请求（3/3 生成全中），降级虽优雅但永久白付往返与日志噪音。
"""
import asyncio
from unittest.mock import patch

import app.utils.rerank_utils as ru


def _reset():
    ru._rerank_failures.clear()


def _run(**kwargs):
    return asyncio.run(ru.rerank_documents("查询", ["文档一", "文档二"], **kwargs))


def test_latches_after_threshold_and_stops_calling():
    """连续失败达阈值后不再发起请求。"""
    _reset()
    calls = {"n": 0}

    class _Boom:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k):
            calls["n"] += 1
            raise RuntimeError("503 Service Unavailable")

    with patch.object(
        ru, "_resolve_rerank_config",
        return_value=("https://dead.example.com/v1/rerank", "k", "m"),
    ), patch.object(ru.httpx, "AsyncClient", _Boom):
        for _ in range(ru._RERANK_FAILURE_THRESHOLD):
            assert _run() is None
        assert calls["n"] == ru._RERANK_FAILURE_THRESHOLD

        # 熄火后再调用若干次，不应再产生任何请求
        for _ in range(5):
            assert _run() is None
        assert calls["n"] == ru._RERANK_FAILURE_THRESHOLD


def test_success_resets_failure_counter():
    """成功一次即清零，偶发抖动不会累积成熄火。"""
    _reset()
    url = "https://ok.example.com/v1/rerank"
    ru._rerank_failures[url] = ru._RERANK_FAILURE_THRESHOLD - 1

    class _Ok:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return _Resp()

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"results": [{"index": 0, "relevance_score": 0.9}]}

    with patch.object(
        ru, "_resolve_rerank_config", return_value=(url, "k", "m"),
    ), patch.object(ru.httpx, "AsyncClient", _Ok):
        assert _run() is not None

    assert url not in ru._rerank_failures
