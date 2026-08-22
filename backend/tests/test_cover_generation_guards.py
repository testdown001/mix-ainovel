"""AI 封面能力的档位、计费、互斥、失败退款与文件清理。"""
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import app.models  # noqa: F401
from app.api.routers import novels
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.credit_log import CreditLog
from app.models.novel import NovelProject
from app.schemas.user import UserInDB
from app.services.generation_billing_service import (
    charge_cover_generation,
    cover_generation_price,
    refund_generation,
)
from app.services.novel_service import NovelService
from app.services.quota_service import QuotaService

OWNER = UserInDB(id=71, username="cover-owner", hashed_password="x")
FREE_USER = UserInDB(id=72, username="cover-free", hashed_password="x")
PROJECT_ID = "cover-guard-project"


def _client(db_session, user=OWNER, *, raise_app_exceptions=True):
    test_app = FastAPI()
    test_app.include_router(novels.router)

    async def _session():
        yield db_session

    async def _user():
        return user

    test_app.dependency_overrides[get_session] = _session
    test_app.dependency_overrides[get_current_user] = _user
    return AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=raise_app_exceptions),
        base_url="http://test",
    )


async def _quota(db, user_id: int, *, tier: str, credits: int = 50):
    quota = await QuotaService(db).get_or_create_quota(user_id)
    quota.is_premium = tier != "free"
    quota.plan_tier = tier
    quota.credit_balance = credits
    quota.credit_purchased = 0
    await db.commit()
    return quota


async def _project(db, user_id: int, project_id: str = PROJECT_ID):
    db.add(NovelProject(id=project_id, user_id=user_id, title="封面守卫测试", initial_prompt="东方玄幻"))
    await db.commit()


@pytest.mark.asyncio
async def test_cover_price_charge_and_refund_are_idempotent(db_session):
    await _quota(db_session, OWNER.id, tier="creator", credits=50)
    assert await cover_generation_price(db_session) == 10
    assert await charge_cover_generation(db_session, OWNER.id, ref_key="cover-ref") == 10
    assert await charge_cover_generation(db_session, OWNER.id, ref_key="cover-ref") == 10
    quota = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert quota.credit_balance == 40
    rows = (
        await db_session.execute(select(CreditLog).where(CreditLog.reason == "cover_generation"))
    ).scalars().all()
    assert len(rows) == 1
    assert await refund_generation(db_session, OWNER.id, ref_key="cover-ref") == 10
    assert await refund_generation(db_session, OWNER.id, ref_key="cover-ref") == 0


@pytest.mark.asyncio
async def test_cover_options_and_free_tier_guard(db_session, monkeypatch):
    await _quota(db_session, FREE_USER.id, tier="free", credits=50)
    await _project(db_session, FREE_USER.id)
    generate = AsyncMock(side_effect=AssertionError("免费档不应调用图片模型"))
    monkeypatch.setattr(novels.LLMService, "generate_image", generate)

    async with _client(db_session, FREE_USER) as client:
        options = await client.get(f"/api/novels/{PROJECT_ID}/cover/options")
        denied = await client.post(f"/api/novels/{PROJECT_ID}/cover/generate", json={})

    assert options.status_code == 200
    assert options.json() == {
        "tier": "free",
        "required_tier": "creator",
        "can_generate": False,
        "credit_price": 10,
    }
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "FEATURE_NOT_AVAILABLE"
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_cover_generation_charges_and_persists(db_session, monkeypatch, tmp_path):
    await _quota(db_session, OWNER.id, tier="creator", credits=50)
    await _project(db_session, OWNER.id)
    monkeypatch.setattr(settings, "cover_storage_dir", str(tmp_path))
    monkeypatch.setattr(
        novels.CacheService,
        "acquire_distributed_lock",
        AsyncMock(return_value=True),
    )
    release = AsyncMock(return_value=True)
    monkeypatch.setattr(novels.CacheService, "release_distributed_lock", release)
    monkeypatch.setattr(
        novels.LLMService,
        "generate_image",
        AsyncMock(return_value=(b"\x89PNG\r\n\x1a\nmock", "gpt-image-2")),
    )

    async with _client(db_session) as client:
        response = await client.post(f"/api/novels/{PROJECT_ID}/cover/generate", json={})

    assert response.status_code == 200
    assert response.json()["charged"] == 10
    assert (tmp_path / f"{PROJECT_ID}.image").read_bytes().startswith(b"\x89PNG")
    quota = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert quota.credit_balance == 40
    release.assert_awaited_once()


@pytest.mark.asyncio
async def test_cover_generation_busy_does_not_charge(db_session, monkeypatch):
    await _quota(db_session, OWNER.id, tier="creator", credits=50)
    await _project(db_session, OWNER.id)
    monkeypatch.setattr(
        novels.CacheService,
        "acquire_distributed_lock",
        AsyncMock(return_value=False),
    )

    async with _client(db_session) as client:
        response = await client.post(f"/api/novels/{PROJECT_ID}/cover/generate", json={})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GENERATION_IN_PROGRESS"
    quota = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert quota.credit_balance == 50


@pytest.mark.asyncio
async def test_cover_generation_insufficient_credits_never_calls_provider(db_session, monkeypatch):
    await _quota(db_session, OWNER.id, tier="creator", credits=5)
    await _project(db_session, OWNER.id)
    monkeypatch.setattr(
        novels.CacheService,
        "acquire_distributed_lock",
        AsyncMock(return_value=True),
    )
    release = AsyncMock(return_value=True)
    monkeypatch.setattr(novels.CacheService, "release_distributed_lock", release)
    generate = AsyncMock(side_effect=AssertionError("余额不足不应调用图片模型"))
    monkeypatch.setattr(novels.LLMService, "generate_image", generate)

    async with _client(db_session) as client:
        response = await client.post(f"/api/novels/{PROJECT_ID}/cover/generate", json={})

    assert response.status_code == 402
    generate.assert_not_awaited()
    release.assert_awaited_once()
    quota = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert quota.credit_balance == 5


@pytest.mark.asyncio
async def test_cover_failure_refunds_and_delete_cleans_file(db_session, monkeypatch, tmp_path):
    await _quota(db_session, OWNER.id, tier="creator", credits=50)
    await _project(db_session, OWNER.id)
    monkeypatch.setattr(settings, "cover_storage_dir", str(tmp_path))
    monkeypatch.setattr(
        novels.CacheService,
        "acquire_distributed_lock",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        novels.CacheService,
        "release_distributed_lock",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        novels.LLMService,
        "generate_image",
        AsyncMock(side_effect=RuntimeError("image provider down")),
    )

    async with _client(db_session, raise_app_exceptions=False) as client:
        response = await client.post(f"/api/novels/{PROJECT_ID}/cover/generate", json={})
    assert response.status_code == 500
    quota = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert quota.credit_balance == 50

    cover_file = tmp_path / f"{PROJECT_ID}.image"
    cover_file.write_bytes(b"old cover")
    await NovelService(db_session).delete_projects([PROJECT_ID], OWNER.id)
    assert not cover_file.exists()
