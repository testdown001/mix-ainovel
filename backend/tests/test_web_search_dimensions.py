"""参考小说多维度检索的降级与组合。

此前分析一本书只发一次检索，几百万字压进一段百科式摘要，三路抽取全吃同一段——
「剧情思考不深」的根源在输入就没有料。多维度检索的契约：
- 单维度失败降级（少一路素材），全部失败才 502；
- 维度结果独立缓存（重新分析不重付全部检索成本）；
- combine_dimension_texts 请求的维度全缺失时回退到可用维度，绝不给抽取端空输入。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.web_search_service import WebSearchService


class _FakeCache:
    """签名必须与真 CacheService.set(key, value, ttl=None) 一致。

    上一版假对象写成 expire=，测试全绿、线上五路检索全灭——TypeError 是真服务抛的。
    假对象不镜像真实 API，测试守的就是一个不存在的世界。
    """

    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=None):
        assert ttl is not None, "维度缓存必须带 TTL"
        self.store[key] = value


def _service(response_map):
    """response_map: 维度关键词 → 返回文本 或 Exception。"""
    svc = WebSearchService.__new__(WebSearchService)
    svc.cache_service = _FakeCache()
    calls = []

    async def _search(system_prompt, conversation_history, **_kw):
        content = conversation_history[0]["content"]
        for keyword, outcome in response_map.items():
            if keyword in content:
                calls.append(keyword)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise AssertionError(f"未匹配任何维度: {content[:80]}")

    svc.llm_service = SimpleNamespace(
        _resolve_search_llm_config=AsyncMock(return_value={}),
        get_search_llm_response=_search,
    )
    svc._calls = calls
    return svc


def test_partial_dimension_failure_degrades():
    svc = _service({
        "主线剧情的完整走向": "剧情内容",
        "主要角色的身份": RuntimeError("超时"),
        "名场面和经典桥段": "桥段内容",
        "爽点的类型": RuntimeError("超时"),
        "叙事视角与人称": "写法内容",
    })
    result = asyncio.run(svc.search_novel_dimensions(novel_name="某书"))
    assert set(result) == {"plot", "beats", "craft"}
    assert result["beats"] == "桥段内容"


def test_all_dimensions_failed_raises_502():
    svc = _service({
        "主线剧情的完整走向": RuntimeError("x"),
        "主要角色的身份": RuntimeError("x"),
        "名场面和经典桥段": RuntimeError("x"),
        "爽点的类型": RuntimeError("x"),
        "叙事视角与人称": RuntimeError("x"),
    })
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.search_novel_dimensions(novel_name="某书"))
    assert exc.value.status_code == 502


def test_dimension_results_are_cached_per_dimension():
    svc = _service({
        "主线剧情的完整走向": "剧情内容",
        "名场面和经典桥段": "桥段内容",
    })
    asyncio.run(svc.search_novel_dimensions(novel_name="某书", dimensions=["plot", "beats"]))
    asyncio.run(svc.search_novel_dimensions(novel_name="某书", dimensions=["plot", "beats"]))
    # 第二次全部命中缓存，不再发检索
    assert len(svc._calls) == 2


def test_combine_falls_back_to_available_dimensions():
    results = {"craft": "写法内容"}
    combined = WebSearchService.combine_dimension_texts(results, "beats", "pacing")
    # 请求的维度全缺失 → 回退全部可用维度，抽取端拿到的永远不是空串
    assert "写法内容" in combined

    combined2 = WebSearchService.combine_dimension_texts(
        {"plot": "剧情", "beats": "桥段"}, "beats", "pacing"
    )
    assert "桥段" in combined2 and "剧情" not in combined2
    assert "【名场面与桥段】" in combined2


def test_unknown_dimension_names_ignored():
    svc = _service({"主线剧情的完整走向": "剧情内容"})
    result = asyncio.run(svc.search_novel_dimensions(novel_name="某书", dimensions=["plot", "nope"]))
    assert set(result) == {"plot"}
