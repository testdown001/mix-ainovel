"""蓝图深度打磨积分计费：只对真正会跑审稿/修订的 deep 路径先扣后跑。

覆盖：
- deep + 档位允许 + 审稿门开 + 余额足够 → 扣费，同 ref_key 幂等
- deep + 余额不足 → 402，不进入生成
- fast → 不扣
- deep 但档位降级为 fast → 不扣
- review_enabled=false → 不扣（等价快速成书）
- 扣费后失败 → 退一次，重放退款 no-op
- 单价来自 SystemConfig（覆写 20 → N）
- GET /concept/dossier 返回 deep_credit_price
"""
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import app.models  # noqa: F401
from app.api.routers import novels
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.credit_log import CreditLog
from app.models.novel import NovelProject
from app.models.system_config import SystemConfig
from app.models.user_quota import UserQuota
from app.schemas.novel import Blueprint, BlueprintGenerationResponse
from app.schemas.user import UserInDB
from app.services.generation_billing_service import (
    blueprint_deep_price,
    charge_blueprint_deep,
    refund_generation,
    should_charge_blueprint_deep,
)
from app.services.quota_service import QuotaService

OWNER = UserInDB(id=21, username="creator", hashed_password="x")
FREE_USER = UserInDB(id=22, username="free", hashed_password="x")
PROJECT_ID = "proj-bp-billing"


def _build_client(db_session, user=OWNER):
    test_app = FastAPI()
    test_app.include_router(novels.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return user

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


async def _creator_quota(db, user_id: int, credits: int = 100) -> UserQuota:
    svc = QuotaService(db)
    q = await svc.get_or_create_quota(user_id)
    q.is_premium = True
    q.plan_tier = "creator"
    q.credit_balance = credits
    q.credit_purchased = 0
    await db.commit()
    await db.refresh(q)
    return q


async def _seed_project(db, user_id: int, project_id: str = PROJECT_ID):
    db.add(NovelProject(
        id=project_id,
        user_id=user_id,
        title="计费测试",
        concept_dossier={"dossier": {"core_selling_line": "卖点"}, "generated_at": "t"},
    ))
    await db.commit()


def _fake_blueprint_response():
    return BlueprintGenerationResponse(
        blueprint=Blueprint(title="计费蓝图"),
        ai_message="ok",
    )


@pytest.mark.asyncio
async def test_should_charge_fast_is_false(db_session):
    await _creator_quota(db_session, OWNER.id)
    assert await should_charge_blueprint_deep(db_session, OWNER.id, "fast") is False


@pytest.mark.asyncio
async def test_should_charge_free_tier_degrades(db_session):
    await QuotaService(db_session).get_or_create_quota(FREE_USER.id)
    assert await should_charge_blueprint_deep(db_session, FREE_USER.id, "deep") is False


@pytest.mark.asyncio
async def test_should_charge_review_disabled(db_session):
    await _creator_quota(db_session, OWNER.id)
    db_session.add(SystemConfig(key="blueprint.review_enabled", value="false"))
    await db_session.commit()
    assert await should_charge_blueprint_deep(db_session, OWNER.id, "deep") is False


@pytest.mark.asyncio
async def test_should_charge_deep_creator_default_on(db_session):
    await _creator_quota(db_session, OWNER.id)
    assert await should_charge_blueprint_deep(db_session, OWNER.id, "deep") is True


@pytest.mark.asyncio
async def test_price_default_and_override(db_session):
    assert await blueprint_deep_price(db_session) == 20
    db_session.add(SystemConfig(key="credits.price.blueprint_deep", value="35"))
    await db_session.commit()
    assert await blueprint_deep_price(db_session) == 35


@pytest.mark.asyncio
async def test_charge_idempotent_and_refund_once(db_session):
    await _creator_quota(db_session, OWNER.id, credits=80)
    charged = await charge_blueprint_deep(db_session, OWNER.id, ref_key="bp-ref-1")
    assert charged == 20
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 60
    # 同 ref 不重复扣
    assert await charge_blueprint_deep(db_session, OWNER.id, ref_key="bp-ref-1") == 20
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 60
    row = (
        await db_session.execute(
            select(CreditLog).where(CreditLog.reason == "blueprint_deep", CreditLog.ref_key == "bp-ref-1")
        )
    ).scalar_one()
    assert row.delta == -20
    assert "blueprint_deep_unit=20" in (row.note or "")
    assert await refund_generation(db_session, OWNER.id, ref_key="bp-ref-1") == 20
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 80
    assert await refund_generation(db_session, OWNER.id, ref_key="bp-ref-1") == 0
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 80


@pytest.mark.asyncio
async def test_charge_uses_config_price_in_note(db_session):
    await _creator_quota(db_session, OWNER.id, credits=80)
    db_session.add(SystemConfig(key="credits.price.blueprint_deep", value="35"))
    await db_session.commit()
    assert await charge_blueprint_deep(db_session, OWNER.id, ref_key="bp-ref-price") == 35
    row = (
        await db_session.execute(
            select(CreditLog).where(CreditLog.ref_key == "bp-ref-price")
        )
    ).scalar_one()
    assert "blueprint_deep_unit=35" in (row.note or "")
    # 改价后再退，仍按当时单价
    row_cfg = (
        await db_session.execute(
            select(SystemConfig).where(SystemConfig.key == "credits.price.blueprint_deep")
        )
    ).scalar_one()
    row_cfg.value = "99"
    await db_session.commit()
    assert await refund_generation(db_session, OWNER.id, ref_key="bp-ref-price") == 35


@pytest.mark.asyncio
async def test_charge_insufficient_402(db_session):
    await _creator_quota(db_session, OWNER.id, credits=5)
    with pytest.raises(HTTPException) as ei:
        await charge_blueprint_deep(db_session, OWNER.id, ref_key="bp-poor")
    assert ei.value.status_code == 402
    assert "积分不足" in str(ei.value.detail)
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 5
    assert (
        await db_session.execute(select(CreditLog).where(CreditLog.ref_key == "bp-poor"))
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_sync_generate_deep_charges(db_session, monkeypatch):
    await _creator_quota(db_session, OWNER.id, credits=80)
    await _seed_project(db_session, OWNER.id)
    gen = AsyncMock(return_value=_fake_blueprint_response())
    monkeypatch.setattr(novels, "generate_blueprint_for_project", gen)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate", json={"depth": "deep"})
    assert resp.status_code == 200
    gen.assert_awaited_once()
    assert gen.await_args.kwargs.get("paid_deep") is True
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 60
    logs = (
        await db_session.execute(select(CreditLog).where(CreditLog.reason == "blueprint_deep"))
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].ref_key.startswith(f"blueprint:{PROJECT_ID}:")


@pytest.mark.asyncio
async def test_sync_generate_deep_insufficient_no_generate(db_session, monkeypatch):
    await _creator_quota(db_session, OWNER.id, credits=3)
    await _seed_project(db_session, OWNER.id)
    gen = AsyncMock(side_effect=AssertionError("积分不足不应生成"))
    monkeypatch.setattr(novels, "generate_blueprint_for_project", gen)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate", json={"depth": "deep"})
    assert resp.status_code == 402
    assert "积分不足" in resp.text
    gen.assert_not_awaited()
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 3


@pytest.mark.asyncio
async def test_sync_generate_fast_no_charge(db_session, monkeypatch):
    await _creator_quota(db_session, OWNER.id, credits=80)
    await _seed_project(db_session, OWNER.id)
    gen = AsyncMock(return_value=_fake_blueprint_response())
    monkeypatch.setattr(novels, "generate_blueprint_for_project", gen)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate", json={"depth": "fast"})
    assert resp.status_code == 200
    assert gen.await_args.kwargs.get("paid_deep") is False
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 80


@pytest.mark.asyncio
async def test_sync_generate_free_tier_deep_no_charge(db_session, monkeypatch):
    await QuotaService(db_session).get_or_create_quota(FREE_USER.id)
    await _seed_project(db_session, FREE_USER.id)
    gen = AsyncMock(return_value=_fake_blueprint_response())
    monkeypatch.setattr(novels, "generate_blueprint_for_project", gen)

    async with _build_client(db_session, FREE_USER) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate", json={"depth": "deep"})
    assert resp.status_code == 200
    assert gen.await_args.kwargs.get("paid_deep") is False
    q = await QuotaService(db_session).get_or_create_quota(FREE_USER.id)
    assert q.credit_balance == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS


@pytest.mark.asyncio
async def test_sync_generate_review_off_no_charge(db_session, monkeypatch):
    await _creator_quota(db_session, OWNER.id, credits=80)
    await _seed_project(db_session, OWNER.id)
    db_session.add(SystemConfig(key="blueprint.review_enabled", value="false"))
    await db_session.commit()
    gen = AsyncMock(return_value=_fake_blueprint_response())
    monkeypatch.setattr(novels, "generate_blueprint_for_project", gen)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate", json={"depth": "deep"})
    assert resp.status_code == 200
    assert gen.await_args.kwargs.get("paid_deep") is False
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    assert q.credit_balance == 80


@pytest.mark.asyncio
async def test_sync_generate_failure_refunds(db_session, monkeypatch):
    await _creator_quota(db_session, OWNER.id, credits=80)
    await _seed_project(db_session, OWNER.id)
    gen = AsyncMock(side_effect=HTTPException(status_code=502, detail="章纲生成不完整"))
    monkeypatch.setattr(novels, "generate_blueprint_for_project", gen)
    refund = AsyncMock()
    monkeypatch.setattr(novels, "refund_blueprint_safely", refund)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate", json={"depth": "deep"})
    assert resp.status_code == 502
    refund.assert_awaited_once()
    q = await QuotaService(db_session).get_or_create_quota(OWNER.id)
    # 真实退款走独立 session（测试里被桩掉），主 session 上的扣费仍在
    assert q.credit_balance == 60


@pytest.mark.asyncio
async def test_dossier_exposes_deep_credit_price(db_session):
    await _creator_quota(db_session, OWNER.id)
    await _seed_project(db_session, OWNER.id, "proj-dossier-price")
    # creator 有压力推演：补一份报告避免 GET 同步跑 LLM
    proj = await db_session.get(NovelProject, "proj-dossier-price")
    proj.concept_dossier = {
        "dossier": {"core_selling_line": "卖点"},
        "stress_report": {"overall_verdict": "可开工"},
        "generated_at": "t",
    }
    await db_session.commit()

    async with _build_client(db_session) as client:
        resp = await client.get("/api/novels/proj-dossier-price/concept/dossier")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deep_available"] is True
    assert body["deep_credit_price"] == 20


@pytest.mark.asyncio
async def test_dossier_price_zero_when_review_disabled(db_session):
    await _creator_quota(db_session, OWNER.id)
    await _seed_project(db_session, OWNER.id, "proj-dossier-off")
    proj = await db_session.get(NovelProject, "proj-dossier-off")
    proj.concept_dossier = {
        "dossier": {"core_selling_line": "卖点"},
        "stress_report": {"overall_verdict": "可开工"},
        "generated_at": "t",
    }
    db_session.add(SystemConfig(key="blueprint.review_enabled", value="false"))
    await db_session.commit()

    async with _build_client(db_session) as client:
        resp = await client.get("/api/novels/proj-dossier-off/concept/dossier")
    assert resp.status_code == 200
    assert resp.json()["deep_credit_price"] == 0
    assert resp.json()["deep_available"] is True
