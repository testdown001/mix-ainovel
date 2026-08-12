"""加油包支付回归：目录解析 + 回调激活分流 + 幂等。

- list_credit_packs：默认三档；SystemConfig credits.packs 覆写；非法项过滤/坏 JSON 回退
- _activate_membership：plan_id=0 + remark=credit_pack:{code}:{credits} 的订单
  → 积分入永久池（按订单号幂等），不走会员升级
"""
import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
from app.models.payment_order import PaymentOrder
from app.models.system_config import SystemConfig
from app.services.payment_service import DEFAULT_CREDIT_PACKS, PaymentService
from app.services.quota_service import QuotaService


@pytest.mark.asyncio
async def test_list_credit_packs_defaults(db_session):
    svc = PaymentService(db_session)
    packs = await svc.list_credit_packs()
    assert packs == DEFAULT_CREDIT_PACKS
    assert all(p["credits"] > 0 and p["price"] > 0 for p in packs)


@pytest.mark.asyncio
async def test_list_credit_packs_config_override_and_filtering(db_session):
    db_session.add(SystemConfig(
        key="credits.packs",
        value='[{"code":"mini","name":"迷你包","credits":100,"price":3},'
              '{"code":"bad:colon","name":"非法码","credits":100,"price":3},'
              '{"code":"zero","name":"零积分","credits":0,"price":3}]',
    ))
    await db_session.commit()

    svc = PaymentService(db_session)
    packs = await svc.list_credit_packs()
    # 仅合法项生效：含冒号的 code 与 credits<=0 的项被过滤
    assert [p["code"] for p in packs] == ["mini"]
    assert (await svc.get_credit_pack("mini"))["credits"] == 100
    assert await svc.get_credit_pack("bad:colon") is None


@pytest.mark.asyncio
async def test_list_credit_packs_bad_json_falls_back(db_session):
    db_session.add(SystemConfig(key="credits.packs", value="not-json"))
    await db_session.commit()
    svc = PaymentService(db_session)
    assert await svc.list_credit_packs() == DEFAULT_CREDIT_PACKS


@pytest.mark.asyncio
async def test_pack_order_activation_credits_purchased_pool(db_session):
    """加油包订单支付成功 → 永久池入账；重复激活（回调重放）幂等。"""
    quota_svc = QuotaService(db_session)
    await quota_svc.get_or_create_quota(11)  # 月度 60

    order = PaymentOrder(
        order_no="APTESTPACK001",
        user_id=11,
        plan_id=0,
        plan_name="加油包·300积分",
        amount=6.0,
        currency="CNY",
        channel="alipay",
        status="paid",
        remark="credit_pack:pack_300:300",
    )
    db_session.add(order)
    await db_session.commit()

    svc = PaymentService(db_session)
    await svc._activate_membership(order)
    q = await quota_svc.get_quota(11)
    assert q.credit_purchased == 300
    assert q.credit_balance == 60  # 月度池不动
    assert q.is_premium is False   # 不误升会员

    # 回调重放：不重复入账
    await svc._activate_membership(order)
    q = await quota_svc.get_quota(11)
    assert q.credit_purchased == 300


@pytest.mark.asyncio
async def test_pack_order_with_broken_remark_is_noop(db_session):
    quota_svc = QuotaService(db_session)
    await quota_svc.get_or_create_quota(12)

    order = PaymentOrder(
        order_no="APTESTPACK002",
        user_id=12,
        plan_id=0,
        plan_name="加油包·坏标记",
        amount=6.0,
        currency="CNY",
        channel="alipay",
        status="paid",
        remark="credit_pack:oops",  # 缺 credits 段 → rsplit 后非数字
    )
    db_session.add(order)
    await db_session.commit()

    svc = PaymentService(db_session)
    await svc._activate_membership(order)  # 不抛异常、不入账
    q = await quota_svc.get_quota(12)
    assert (q.credit_purchased or 0) == 0
