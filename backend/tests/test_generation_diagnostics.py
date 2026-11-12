from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.generation_diagnostics_service import build_diagnostic, record_failure, redact
from app.services.generation_quality_gate import GenerationQualityError


def request():
    return SimpleNamespace(task_id="task", execution_id="attempt", project_id="novel",
                           chapter_number=2, task_type="chapter:generate")


def test_quality_report_is_preserved_without_manuscript():
    error = GenerationQualityError("检查失败", report={"issues": [{
        "category": "causality", "severity": "blocking", "evidence": "门已锁上",
        "explanation": "没有开门却直接进入", "secret": "never-store"}]}, partial_text="manuscript-private")
    record = build_diagnostic(request(), error, "verify_before_commit")
    assert record["issues"][0]["explanation"] == "没有开门却直接进入"
    assert record["execution_id"] == "attempt"
    assert "manuscript-private" not in str(record)
    assert "never-store" not in str(record)


def test_nested_quality_error_and_redaction():
    inner = GenerationQualityError("inner", report={"issues": [{"evidence": "proof"}]})
    outer = RuntimeError("Authorization: Bearer confidential123 api_key=private123 https://user:pass@host/")
    outer.__cause__ = inner
    record = build_diagnostic(request(), outer)
    assert record["issues"][0]["evidence"] == "proof"
    for secret in ("confidential123", "private123", "user:pass"):
        assert secret not in str(record)
    assert len(redact("x" * 50000)) == 20000


@pytest.mark.asyncio
async def test_atomic_bounded_retention():
    pipe = MagicMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.execute = AsyncMock()
    redis = MagicMock()
    redis.pipeline.return_value = pipe
    with patch("app.services.generation_diagnostics_service.CacheService._get_redis", AsyncMock(return_value=redis)):
        await record_failure(request(), RuntimeError("failed"))
    pipe.ltrim.assert_called_once_with("arboris:generation_diagnostics:novel", 0, 99)
    pipe.expire.assert_called_once_with("arboris:generation_diagnostics:novel", 2592000)
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_storage_failure_does_not_break_task_failure_handling():
    with patch("app.services.generation_diagnostics_service.CacheService._get_redis", AsyncMock(side_effect=RuntimeError("offline"))):
        await record_failure(request(), RuntimeError("generation failed"))


@pytest.mark.asyncio
async def test_admin_endpoint_forbids_regular_user():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.api.routers import admin
    from app.core.dependencies import get_current_user
    from app.db.session import get_session

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=False)
    app.dependency_overrides[get_session] = lambda: AsyncMock()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/admin/novels/359f7628-d309-4b2a-bbad-66a1f1438a95/generation-diagnostics")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_returns_structured_report():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.api.routers import admin
    from app.core.dependencies import get_current_admin
    from app.db.session import get_session

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(is_admin=True)
    session = AsyncMock()
    session.get.return_value = object()
    app.dependency_overrides[get_session] = lambda: session
    with patch("app.services.generation_diagnostics_service.list_failures", AsyncMock(return_value=[{"id": "diagnostic"}])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/admin/novels/359f7628-d309-4b2a-bbad-66a1f1438a95/generation-diagnostics")
    assert response.status_code == 200
    assert response.json()["records"] == [{"id": "diagnostic"}]
