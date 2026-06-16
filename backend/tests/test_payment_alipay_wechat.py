"""支付宝 / 微信回调：验签 + 金额校验 + 幂等 + 激活会员（真内存 SQLite，不触网）。

支付 SDK 客户端通过替换 `_build_alipay_client` / `_build_wechat_client` 注入 MagicMock，
故无需真实密钥、不发起任何网络请求。补齐此前仅 Stripe 有回调测试的盲区
（见 tests/test_payment_stripe.py 同款模式）。
"""
import asyncio
from unittest.mock import MagicMock

import app.models  # noqa: F401  触发 SQLAlchemy mapper 注册（含 UserQuota）
from app.db.base import Base
from app.models.plan import Plan
from app.models.payment_order import PaymentOrder
from app.services.payment_service import PaymentService
from app.services.quota_service import QuotaService

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _seed(session, *, channel, order_no, amount=68):
    session.add(Plan(id=2, name="创作者版", tier="creator", price=68, period="monthly",
                     daily_chapter_limit=30, max_novels=20))
    session.add(PaymentOrder(order_no=order_no, user_id=1, plan_id=2, plan_name="创作者版",
                             amount=amount, currency="CNY", channel=channel, status="pending"))
    await session.commit()


async def _order_status(session, order_no):
    return (await session.execute(
        select(PaymentOrder).where(PaymentOrder.order_no == order_no)
    )).scalar_one().status


# ============================== 支付宝 ==============================

def _alipay_data(*, total_amount="68.00", trade_status="TRADE_SUCCESS", out_trade_no="ALI_1"):
    return {
        "sign": "fake-sign", "sign_type": "RSA2",
        "trade_status": trade_status, "out_trade_no": out_trade_no,
        "trade_no": "ALI_TXN_1", "total_amount": total_amount,
    }


def _alipay_svc(session, *, verify_result=True):
    svc = PaymentService(session)
    client = MagicMock()
    client.verify.return_value = verify_result
    svc._build_alipay_client = lambda cfg: client  # 注入 mock，绕过真实 AliPay SDK
    return svc


def test_alipay_valid_signature_activates_membership():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="alipay", order_no="ALI_1")
            svc = _alipay_svc(session, verify_result=True)
            order = await svc.verify_alipay_callback(_alipay_data())
            assert order is not None and order.status == "paid"
            assert order.transaction_id == "ALI_TXN_1"
            quota = await QuotaService(session).get_or_create_quota(1)
            assert quota.is_premium is True and quota.plan_tier == "creator"
        await engine.dispose()
    asyncio.run(_run())


def test_alipay_invalid_signature_returns_none():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="alipay", order_no="ALI_1")
            svc = _alipay_svc(session, verify_result=False)
            order = await svc.verify_alipay_callback(_alipay_data())
            assert order is None
            assert await _order_status(session, "ALI_1") == "pending"
            quota = await QuotaService(session).get_or_create_quota(1)
            assert quota.is_premium is False
        await engine.dispose()
    asyncio.run(_run())


def test_alipay_amount_mismatch_does_not_activate():
    """安全关键：签名有效但回调金额与订单不符时，不得激活会员。"""
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="alipay", order_no="ALI_1", amount=68)
            svc = _alipay_svc(session, verify_result=True)
            order = await svc.verify_alipay_callback(_alipay_data(total_amount="0.01"))
            assert order is None
            assert await _order_status(session, "ALI_1") == "pending"
            quota = await QuotaService(session).get_or_create_quota(1)
            assert quota.is_premium is False
        await engine.dispose()
    asyncio.run(_run())


def test_alipay_idempotent_repeat_callback():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="alipay", order_no="ALI_1")
            svc = _alipay_svc(session, verify_result=True)
            o1 = await svc.verify_alipay_callback(_alipay_data())
            o2 = await svc.verify_alipay_callback(_alipay_data())  # 重复回调
            assert o1.status == "paid" and o2.status == "paid"  # 幂等不报错、不重复处理
        await engine.dispose()
    asyncio.run(_run())


# ============================== 微信 ==============================

def _wechat_result(*, total=6800, trade_state="SUCCESS", out_trade_no="WX_1"):
    return {
        "out_trade_no": out_trade_no, "transaction_id": "WX_TXN_1",
        "trade_state": trade_state, "amount": {"total": total, "currency": "CNY"},
    }


def _wechat_svc(session, *, callback_result=None, raises=False):
    svc = PaymentService(session)
    client = MagicMock()
    if raises:
        client.callback.side_effect = Exception("签名验证失败")
    else:
        client.callback.return_value = callback_result
    svc._build_wechat_client = lambda cfg: client  # 注入 mock，绕过真实 wechatpayv3 SDK
    return svc


def test_wechat_valid_callback_activates_membership():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="wechat", order_no="WX_1", amount=68)
            svc = _wechat_svc(session, callback_result=_wechat_result(total=6800))
            order = await svc.verify_wechat_callback({"Wechatpay-Signature": "x"}, "{}")
            assert order is not None and order.status == "paid"
            assert order.transaction_id == "WX_TXN_1"
            quota = await QuotaService(session).get_or_create_quota(1)
            assert quota.is_premium is True and quota.plan_tier == "creator"
        await engine.dispose()
    asyncio.run(_run())


def test_wechat_invalid_signature_returns_none():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="wechat", order_no="WX_1")
            svc = _wechat_svc(session, raises=True)  # client.callback 抛异常 = 验签失败
            order = await svc.verify_wechat_callback({"Wechatpay-Signature": "bad"}, "{}")
            assert order is None
            assert await _order_status(session, "WX_1") == "pending"
            quota = await QuotaService(session).get_or_create_quota(1)
            assert quota.is_premium is False
        await engine.dispose()
    asyncio.run(_run())


def test_wechat_amount_mismatch_does_not_activate():
    """安全关键：解密成功但回调金额（分）与订单不符时，不得激活会员。"""
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="wechat", order_no="WX_1", amount=68)
            svc = _wechat_svc(session, callback_result=_wechat_result(total=1))  # 1 分 ≠ 6800 分
            order = await svc.verify_wechat_callback({"Wechatpay-Signature": "x"}, "{}")
            assert order is None
            assert await _order_status(session, "WX_1") == "pending"
            quota = await QuotaService(session).get_or_create_quota(1)
            assert quota.is_premium is False
        await engine.dispose()
    asyncio.run(_run())


def test_wechat_idempotent_repeat_callback():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session, channel="wechat", order_no="WX_1")
            svc = _wechat_svc(session, callback_result=_wechat_result())
            o1 = await svc.verify_wechat_callback({"Wechatpay-Signature": "x"}, "{}")
            o2 = await svc.verify_wechat_callback({"Wechatpay-Signature": "x"}, "{}")  # 重复回调
            assert o1.status == "paid" and o2.status == "paid"
        await engine.dispose()
    asyncio.run(_run())
