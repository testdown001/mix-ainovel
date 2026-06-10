"""llm_fallback 兜底通道回归（get_llm_response 默认通道失败时自动重试一次）。

锁定四条行为边界：
1. 默认通道失败且兜底已配置 → 用 config_override + api_type="fallback" 重试并返回结果；
2. 兜底未配置（api_key 缺失）→ 原始异常原样抛出；
3. 429（用户每日请求上限）→ 属配额问题，不触发兜底；
4. 已向调用方流出增量（on_chunk 已触发）→ 不兜底，避免重复输出。
"""
import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import app.models  # noqa: F401  触发 mapper 注册
from app.services.llm_service import LLMService

_FALLBACK_CONFIG = {
    "api_key": "fb-key",
    "base_url": "https://fallback.example.com/v1",
    "model": "fb-model",
    "api_format": None,
    "reasoning_effort": None,
}


def _service() -> LLMService:
    return LLMService(session=None)


def test_fallback_retries_once_when_default_fails(monkeypatch):
    svc = _service()
    calls = []

    async def fake_stream(messages, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise HTTPException(status_code=503, detail="AI 服务连接失败")
        return "兜底成功"

    monkeypatch.setattr(svc, "_stream_and_collect", fake_stream)
    monkeypatch.setattr(
        svc, "_resolve_fallback_llm_config", AsyncMock(return_value=dict(_FALLBACK_CONFIG))
    )

    out = asyncio.run(svc.get_llm_response("system", [{"role": "user", "content": "hi"}]))

    assert out == "兜底成功"
    assert len(calls) == 2
    assert calls[1]["api_type"] == "fallback"
    assert calls[1]["config_override"]["api_key"] == "fb-key"
    # 首次调用走默认通道（不带 override）
    assert "config_override" not in calls[0] or calls[0].get("config_override") is None


def test_original_error_raised_when_fallback_unconfigured(monkeypatch):
    svc = _service()

    async def fake_stream(messages, **kwargs):
        raise HTTPException(status_code=502, detail="上游 502")

    monkeypatch.setattr(svc, "_stream_and_collect", fake_stream)
    monkeypatch.setattr(svc, "_resolve_fallback_llm_config", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(svc.get_llm_response("system", [{"role": "user", "content": "hi"}]))
    assert exc_info.value.status_code == 502


def test_daily_limit_429_never_falls_back(monkeypatch):
    svc = _service()
    resolver = AsyncMock(return_value=dict(_FALLBACK_CONFIG))

    async def fake_stream(messages, **kwargs):
        raise HTTPException(status_code=429, detail="今日请求次数已达上限")

    monkeypatch.setattr(svc, "_stream_and_collect", fake_stream)
    monkeypatch.setattr(svc, "_resolve_fallback_llm_config", resolver)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(svc.get_llm_response("system", [{"role": "user", "content": "hi"}]))
    assert exc_info.value.status_code == 429
    resolver.assert_not_awaited()


def test_no_fallback_after_partial_stream_output(monkeypatch):
    svc = _service()
    calls = []

    async def fake_stream(messages, **kwargs):
        calls.append(kwargs)
        on_chunk = kwargs.get("on_chunk")
        if on_chunk is not None:
            on_chunk("部分输出")
        raise HTTPException(status_code=503, detail="流中断")

    monkeypatch.setattr(svc, "_stream_and_collect", fake_stream)
    monkeypatch.setattr(
        svc, "_resolve_fallback_llm_config", AsyncMock(return_value=dict(_FALLBACK_CONFIG))
    )

    received = []
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            svc.get_llm_response(
                "system",
                [{"role": "user", "content": "hi"}],
                on_chunk=received.append,
            )
        )
    assert exc_info.value.status_code == 503
    assert len(calls) == 1  # 已发出增量，不得二次调用
    assert received == ["部分输出"]
