"""管理后台「即将到期用户」名单回归。

到期是订阅制唯一的自动流失点（三渠道都是一次性支付，到期静默回落 free）。
这里钉住三件容易错的事：
1. 路由顺序——`/users/expiring` 必须先于 `/users/{user_id}` 声明，否则 expiring
   会被当成 user_id 去解析，直接 422；
2. 筛选边界——已过期、非会员、窗口外都不该出现在名单里；
3. `has_paid_order`——区分「试用未转化」与「付费用户续费」，两类触达话术不同，
   搞混就是把试用用户当老客催续费。
"""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.models  # noqa: F401  触发全部 mapper 注册
from app.api.routers import admin
from app.core.dependencies import get_current_admin
from app.db.session import get_session
from app.models.payment_order import PaymentOrder
from app.models.user import User
from app.models.user_quota import UserQuota
from app.schemas.user import UserInDB

ADMIN = UserInDB(id=99, username="admin", hashed_password="x", is_admin=True)


def _build_client(db_session):
    test_app = FastAPI()
    test_app.include_router(admin.router)

    async def _override_session():
        yield db_session

    async def _override_admin():
        return ADMIN

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_admin] = _override_admin
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


async def _mk(db, uid, *, days, is_premium=True, tier="creator", credits=0, reminded=False):
    expires = datetime.utcnow() + timedelta(days=days)
    db.add(User(id=uid, username=f"u{uid}", email=f"u{uid}@example.com", hashed_password="x"))
    db.add(
        UserQuota(
            user_id=uid,
            is_premium=is_premium,
            plan_tier=tier,
            premium_expires_at=expires,
            credit_balance=credits,
            expiry_reminded_for=expires if reminded else None,
        )
    )
    await db.commit()


async def _mk_paid_order(db, uid):
    db.add(
        PaymentOrder(
            order_no=f"order-{uid}",
            user_id=uid,
            plan_id=1,
            amount=88,
            channel="alipay",
            status="paid",
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_only_expiring_premium_listed(db_session):
    await _mk(db_session, 1, days=2)                      # ✓ 窗口内
    await _mk(db_session, 2, days=20)                     # ✗ 窗口外
    await _mk(db_session, 3, days=-1)                     # ✗ 已过期
    await _mk(db_session, 4, days=2, is_premium=False)    # ✗ 非会员

    async with _build_client(db_session) as client:
        resp = await client.get("/api/admin/users/expiring?days=7")

    assert resp.status_code == 200
    assert [item["user_id"] for item in resp.json()] == [1]


@pytest.mark.asyncio
async def test_sorted_by_expiry_and_days_left(db_session):
    await _mk(db_session, 11, days=5)
    await _mk(db_session, 12, days=1)
    await _mk(db_session, 13, days=3)

    async with _build_client(db_session) as client:
        resp = await client.get("/api/admin/users/expiring?days=7")

    body = resp.json()
    assert [item["user_id"] for item in body] == [12, 13, 11]
    assert [item["days_left"] for item in body] == [0, 2, 4]  # 不足一天记 0


@pytest.mark.asyncio
async def test_paid_flag_distinguishes_trial_from_customer(db_session):
    await _mk(db_session, 21, days=2)  # 试用，未付费
    await _mk(db_session, 22, days=2)
    await _mk_paid_order(db_session, 22)

    async with _build_client(db_session) as client:
        resp = await client.get("/api/admin/users/expiring?days=7")

    flags = {item["user_id"]: item["has_paid_order"] for item in resp.json()}
    assert flags == {21: False, 22: True}


@pytest.mark.asyncio
async def test_reminded_flag_tracks_current_expiry(db_session):
    await _mk(db_session, 31, days=2, reminded=True)
    await _mk(db_session, 32, days=2, reminded=False)

    async with _build_client(db_session) as client:
        resp = await client.get("/api/admin/users/expiring?days=7")

    flags = {item["user_id"]: item["reminded"] for item in resp.json()}
    assert flags == {31: True, 32: False}


@pytest.mark.asyncio
async def test_days_param_is_clamped(db_session):
    await _mk(db_session, 41, days=60)

    async with _build_client(db_session) as client:
        too_large = await client.get("/api/admin/users/expiring?days=9999")
        too_small = await client.get("/api/admin/users/expiring?days=0")

    # 上限 90 天：60 天后到期的会员在放开的窗口里应可见
    assert [item["user_id"] for item in too_large.json()] == [41]
    # 下限 1 天：不会因为 0 触发空窗或负窗口报错
    assert too_small.status_code == 200
    assert too_small.json() == []


@pytest.mark.asyncio
async def test_credit_total_includes_purchased_pool(db_session):
    expires = datetime.utcnow() + timedelta(days=2)
    db_session.add(User(id=51, username="u51", email="u51@example.com", hashed_password="x"))
    db_session.add(
        UserQuota(
            user_id=51,
            is_premium=True,
            plan_tier="creator",
            premium_expires_at=expires,
            credit_balance=100,
            credit_purchased=250,
        )
    )
    await db_session.commit()

    async with _build_client(db_session) as client:
        resp = await client.get("/api/admin/users/expiring?days=7")

    assert resp.json()[0]["credit_total"] == 350
