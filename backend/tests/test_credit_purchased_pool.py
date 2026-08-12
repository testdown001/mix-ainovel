"""积分双池回归（「月赠清零、充值常驻」拍板落地）：

- 永久池（credit_purchased）由充值入账，不随月度重置清零
- 消费先扣月度池再扣永久池；402 按两池合计判断
- 退款进月度池（防「故意失败洗分」：月度积分不能经退款变成永久积分）
- 充值入账按 (topup, ref_key=订单号) 幂等
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

import app.models  # noqa: F401  触发全部 mapper 注册
from app.services.quota_service import QuotaService


@pytest.mark.asyncio
async def test_topup_goes_to_purchased_pool_and_is_idempotent(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(1)  # 月度池 60

    q = await svc.add_purchased_credits(1, 300, ref_key="AP20260812TEST01", note="充值 加油包·300积分")
    assert q.credit_balance == 60
    assert q.credit_purchased == 300
    assert q.credit_total == 360

    # 支付回调重放：同订单号不重复入账
    q = await svc.add_purchased_credits(1, 300, ref_key="AP20260812TEST01")
    assert q.credit_purchased == 300


@pytest.mark.asyncio
async def test_consume_spends_monthly_pool_first(db_session):
    svc = QuotaService(db_session)
    q = await svc.get_or_create_quota(2)  # 月度池 60
    await svc.add_purchased_credits(2, 100, ref_key="topup2")

    q = await svc.consume_credits(2, 80, reason="generate", ref_key="g2")
    # 先扣光月度 60，再从永久池扣 20
    assert q.credit_balance == 0
    assert q.credit_purchased == 80
    assert q.credit_total == 80


@pytest.mark.asyncio
async def test_402_counts_both_pools(db_session):
    svc = QuotaService(db_session)
    q = await svc.get_or_create_quota(3)  # 月度 60
    await svc.add_purchased_credits(3, 30, ref_key="topup3")  # 总 90

    # 90 >= 70：两池合计足够，不应 402
    q = await svc.consume_credits(3, 70, reason="generate", ref_key="g3a")
    assert q.credit_total == 20

    with pytest.raises(HTTPException) as ei:
        await svc.consume_credits(3, 21, reason="generate", ref_key="g3b")
    assert ei.value.status_code == 402
    # 失败不动账
    q = await svc.get_or_create_quota(3)
    assert q.credit_total == 20


@pytest.mark.asyncio
async def test_monthly_reset_preserves_purchased_pool(db_session):
    svc = QuotaService(db_session)
    q = await svc.get_or_create_quota(4)  # 月度 60，grant 60，默认不累积
    await svc.add_purchased_credits(4, 500, ref_key="topup4")
    await svc.consume_credits(4, 50, reason="generate", ref_key="g4")  # 月度剩 10

    q = await svc.get_or_create_quota(4)
    q.credit_reset_at = datetime.utcnow() - timedelta(days=31)
    await db_session.commit()

    q = await svc.check_and_reset_credit(q)
    # 月度池重置为发放额度，永久池分文不动
    assert q.credit_balance == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS
    assert q.credit_purchased == 500


@pytest.mark.asyncio
async def test_refund_goes_to_monthly_pool_not_purchased(db_session):
    """防洗分：退款回月度池，月度积分不能经「扣费→失败退款」变成永久积分。"""
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(5)  # 月度 60
    await svc.consume_credits(5, 30, reason="generate", ref_key="task5")
    q = await svc.refund_credits(5, 30, ref_key="task5")
    assert q.credit_balance == 60
    assert (q.credit_purchased or 0) == 0
