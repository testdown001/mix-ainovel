"""Anthropic prompt caching 回归：

- system 足够长且未禁用 → 带 cache_control 的内容块数组（稳定前缀跨调用缓存）
- 短 system / 环境变量禁用 / 端点已记闩 → 保持纯字符串（零行为变化）
- 端点 4xx 拒绝缓存块 → 记闩 + 降级纯字符串重试一次（预流失败，不会重复输出）
"""
import asyncio

import httpx
import pytest

from app.utils import llm_tool
from app.utils.llm_tool import AnthropicLLMClient, ChatMessage

LONG_SYSTEM = "你是资深网文作家。" * 300  # 远超 _ANTHROPIC_CACHE_MIN_CHARS
SHORT_SYSTEM = "你是作家。"


@pytest.fixture(autouse=True)
def _clean_latch():
    llm_tool._ANTHROPIC_CACHE_UNSUPPORTED.clear()
    yield
    llm_tool._ANTHROPIC_CACHE_UNSUPPORTED.clear()


def _client(base="https://anthropic.example/v1"):
    return AnthropicLLMClient(api_key="test-key", base_url=base)


def test_long_system_gets_cache_block():
    payload = _client()._build_system_payload(LONG_SYSTEM)
    assert isinstance(payload, list)
    assert payload[0]["type"] == "text"
    assert payload[0]["text"] == LONG_SYSTEM
    assert payload[0]["cache_control"] == {"type": "ephemeral"}


def test_short_system_stays_plain():
    assert _client()._build_system_payload(SHORT_SYSTEM) == SHORT_SYSTEM


def test_env_switch_disables_cache(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_PROMPT_CACHE", "false")
    assert _client()._build_system_payload(LONG_SYSTEM) == LONG_SYSTEM


def test_latched_base_url_stays_plain():
    base = "https://weird-proxy.example/v1"
    llm_tool._ANTHROPIC_CACHE_UNSUPPORTED.add(base)
    assert _client(base)._build_system_payload(LONG_SYSTEM) == LONG_SYSTEM


def test_4xx_on_cache_block_falls_back_and_latches():
    """首次请求带缓存块被 400 拒绝 → 记闩、纯字符串重试，正文照常产出。"""
    base = "https://reject-cache.example/v1"
    client = _client(base)

    seen_systems = []

    async def fake_do_stream(url, payload, timeout):
        seen_systems.append(payload.get("system"))
        if len(seen_systems) == 1:
            req = httpx.Request("POST", url)
            resp = httpx.Response(400, request=req, text="cache_control unsupported")
            raise httpx.HTTPStatusError("bad request", request=req, response=resp)
        yield {"content": "正文", "finish_reason": "stop"}

    client._do_stream = fake_do_stream  # type: ignore[method-assign]

    async def run():
        chunks = []
        async for chunk in client.stream_chat(
            [ChatMessage(role="system", content=LONG_SYSTEM),
             ChatMessage(role="user", content="写一段")],
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())
    assert any(c.get("content") == "正文" for c in chunks)
    # 第一次带缓存块，第二次降级纯字符串
    assert isinstance(seen_systems[0], list)
    assert isinstance(seen_systems[1], str)
    assert base in llm_tool._ANTHROPIC_CACHE_UNSUPPORTED


def test_5xx_propagates_without_latch():
    """5xx 不属于「端点不认缓存块」，照旧抛出走上层重试/fallback，不记闩。"""
    base = "https://flaky.example/v1"
    client = _client(base)

    async def fake_do_stream(url, payload, timeout):
        req = httpx.Request("POST", url)
        resp = httpx.Response(502, request=req, text="bad gateway")
        raise httpx.HTTPStatusError("bad gateway", request=req, response=resp)
        yield  # pragma: no cover - 使函数成为异步生成器

    client._do_stream = fake_do_stream  # type: ignore[method-assign]

    async def run():
        async for _ in client.stream_chat(
            [ChatMessage(role="system", content=LONG_SYSTEM),
             ChatMessage(role="user", content="写一段")],
        ):
            pass

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())
    assert base not in llm_tool._ANTHROPIC_CACHE_UNSUPPORTED
