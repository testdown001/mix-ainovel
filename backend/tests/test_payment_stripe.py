"""Stripe 支付：webhook 签名校验 + 支付完成激活会员 + 渠道门控（真内存 SQLite，不触网）。"""
import asyncio
import hashlib
import hmac
import json
import time

import pytest

import app.models  # noqa: F401  mapper 注册
from app.db.base import Base
from app.models.system_config import SystemConfig
from app.models.plan import Plan
from app.models.payment_order import PaymentOrder
from app.services.payment_service import PaymentService
from app.services.quota_service import QuotaService

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

WEBHOOK_SECRET = "whsec_test_secret"


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


def _sign(payload: bytes, secret: str, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


async def _seed(session, *, enabled="true", secret_key="sk_test", with_order=True):
    session.add(SystemConfig(key="pay.stripe.enabled", value=enabled))
    session.add(SystemConfig(key="pay.stripe.secret_key", value=secret_key))
    session.add(SystemConfig(key="pay.stripe.webhook_secret", value=WEBHOOK_SECRET))
    session.add(Plan(id=2, name="创作者版", tier="creator", price=68, period="monthly",
                     daily_chapter_limit=30, max_novels=20))
    if with_order:
        session.add(PaymentOrder(order_no="ST_TEST_1", user_id=1, plan_id=2, plan_name="创作者版",
                                 amount=68, currency="USD", channel="stripe", status="pending",
                                 transaction_id="cs_test_1"))
    await session.commit()


async def _run_webhook(*, sig_payload_mismatch=False):
    engine, Session = _make_sessionmaker()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as session:
        await _seed(session)
        svc = PaymentService(session)
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"client_reference_id": "ST_TEST_1", "payment_status": "paid",
                                "payment_intent": "pi_123"}},
        }
        payload = json.dumps(event).encode()
        sig = _sign(payload, WEBHOOK_SECRET if not sig_payload_mismatch else "wrong_secret")
        order = await svc.verify_stripe_webhook(payload, sig)
        # 校验激活
        quota = await QuotaService(session).get_or_create_quota(1)
        return order, quota
    await engine.dispose()


def test_stripe_webhook_valid_signature_activates_membership():
    order, quota = asyncio.run(_run_webhook())
    assert order is not None and order.status == "paid"
    assert quota.is_premium is True
    assert quota.plan_tier == "creator"


def test_stripe_webhook_invalid_signature_raises():
    with pytest.raises(PermissionError):
        asyncio.run(_run_webhook(sig_payload_mismatch=True))


def test_stripe_webhook_idempotent():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session)
            svc = PaymentService(session)
            event = {"type": "checkout.session.completed",
                     "data": {"object": {"client_reference_id": "ST_TEST_1", "payment_status": "paid"}}}
            payload = json.dumps(event).encode()
            o1 = await svc.verify_stripe_webhook(payload, _sign(payload, WEBHOOK_SECRET))
            o2 = await svc.verify_stripe_webhook(payload, _sign(payload, WEBHOOK_SECRET))
            assert o1.status == "paid" and o2.status == "paid"  # 第二次幂等不报错
        await engine.dispose()
    asyncio.run(_run())


def test_create_stripe_order_disabled_raises():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, enabled="false", with_order=False)
            svc = PaymentService(session)
            try:
                await svc.create_stripe_order(user_id=1, plan_id=2, plan_name="创作者版", amount=68)
                raise AssertionError("未启用应抛 ValueError")
            except ValueError as e:
                assert "未启用" in str(e)
        await engine.dispose()
    asyncio.run(_run())
