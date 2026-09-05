"""LLM 调用遥测（后台「通道诊断」）回归。

锁定四块：
1. _classify_call_error：超时 vs 错误的归类 + http_status 提取；
2. _percentile：p95 计算；
3. record_call_log：写入一行遥测；
4. /llm-calls/summary 与 /llm-calls 的聚合与过滤（直接调用路由函数，绕过 Depends）。
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

import app.models  # noqa: F401  触发全部 mapper 注册
from app.services.llm_service import LLMService
from app.services.api_usage_recorder import record_call_log
from app.api.routers.admin import _percentile, llm_calls, llm_calls_summary
from app.models.llm_call_log import LLMCallLog
from app.services.api_usage_recorder import prune_call_logs
from sqlalchemy import select


def _svc() -> LLMService:
    return LLMService(session=None)


def test_classify_call_error():
    svc = _svc()
    # 超时类
    assert svc._classify_call_error(httpx.TimeoutException("t")) == ("timeout", None)
    assert svc._classify_call_error(asyncio.TimeoutError()) == ("timeout", None)
    assert svc._classify_call_error(
        HTTPException(status_code=503, detail="AI 服务响应超时，请稍后重试")
    ) == ("timeout", 503)
    # 错误类 + http_status 提取
    assert svc._classify_call_error(HTTPException(status_code=500, detail="boom")) == ("error", 500)
    resp = httpx.Response(429, request=httpx.Request("POST", "https://x"))
    err = httpx.HTTPStatusError("rate", request=resp.request, response=resp)
    assert svc._classify_call_error(err) == ("error", 429)

    class FooTimeoutError(Exception):
        pass

    assert svc._classify_call_error(FooTimeoutError())[0] == "timeout"
    assert svc._classify_call_error(ValueError("x")) == ("error", None)


def test_percentile():
    assert _percentile([], 95) == 0
    assert _percentile([42], 95) == 42
    assert _percentile(list(range(1, 101)), 95) == 95
    assert _percentile(list(range(1, 101)), 100) == 100


@pytest.mark.asyncio
async def test_record_and_summary_and_filter(db_session):
    for lat in (100, 200, 300):
        await record_call_log(db_session, api_type="default", model="m", status="success", latency_ms=lat)
    await record_call_log(
        db_session, api_type="default", status="error", latency_ms=400, http_status=500, error_message="boom"
    )
    await record_call_log(
        db_session, api_type="default", status="timeout", latency_ms=999, http_status=503, error_message="timed out"
    )
    await record_call_log(db_session, api_type="fallback", status="success", latency_ms=50)

    summary = await llm_calls_summary(window="24h", session=db_session, _=None)
    chans = {c["channel"]: c for c in summary["channels"]}
    d = chans["default"]
    assert d["total"] == 5
    assert (d["success"], d["error"], d["timeout"]) == (3, 1, 1)
    assert d["error_rate"] == round(2 / 5, 4)
    assert d["max_latency_ms"] == 999
    assert d["last_error"] in ("boom", "timed out")
    assert chans["fallback"]["total"] == 1
    assert chans["fallback"]["error_rate"] == 0.0

    recent = await llm_calls(limit=100, channel=None, status=None, session=db_session, _=None)
    assert len(recent["calls"]) == 6

    only_err = await llm_calls(limit=100, channel="default", status="error", session=db_session, _=None)
    assert len(only_err["calls"]) == 1
    assert only_err["calls"][0]["error_message"] == "boom"
    assert only_err["calls"][0]["http_status"] == 500


@pytest.mark.asyncio
async def test_retention_filters_and_physically_deletes_expired_rows(db_session):
    now = datetime.utcnow()
    for age in (71, 73, 200):
        db_session.add(LLMCallLog(created_at=now - timedelta(hours=age), status="error"))
    await db_session.commit()
    # 即使定时清理尚未运行，列表和旧客户端 7d 汇总也不能显示过期记录。
    result = await llm_calls(session=db_session, _=None)
    assert len(result["calls"]) == 1
    for window in ("3d", "7d"):
        result = await llm_calls_summary(window=window, session=db_session, _=None)
        assert sum(c["total"] for c in result["channels"]) == 1
    await prune_call_logs(db_session)
    assert len((await db_session.execute(select(LLMCallLog))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_inspiration_diagnostic_has_metadata_without_content(db_session, monkeypatch):
    from contextlib import asynccontextmanager
    from app.services import inspiration_diagnostics as diagnostics

    @asynccontextmanager
    async def session_factory():
        yield db_session

    monkeypatch.setattr(diagnostics, "AsyncSessionLocal", session_factory)
    raw = "secret-novel-content bearer private-key"
    reference = await diagnostics.record_inspiration_error(
        project_id="project-test", user_id=1, raw=raw, kind="invalid_json")
    rows = (await db_session.execute(select(LLMCallLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].error_type == "invalid_json"
    assert reference in rows[0].error_message
    assert "project-test" in rows[0].error_message
    assert raw not in rows[0].error_message
    assert "private-key" not in rows[0].error_message
    await diagnostics.record_inspiration_error(
        project_id="project-test", user_id=1, raw=" \n\t", kind="invalid_json")
    rows = (await db_session.execute(select(LLMCallLog))).scalars().all()
    assert rows[-1].error_type == "empty_response"


@pytest.mark.asyncio
async def test_diagnostic_failure_does_not_mask_generation_error(monkeypatch):
    from app.services import inspiration_diagnostics as diagnostics
    monkeypatch.setattr(diagnostics, "record_call_log", AsyncMock(side_effect=RuntimeError("db down")))
    assert await diagnostics.record_inspiration_error(
        project_id="project-test", user_id=1, raw="bad", kind="invalid_json")
