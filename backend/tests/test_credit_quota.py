"""积分制额度 Phase 1 回归：发放/扣减/不足402/幂等/退款幂等/30天滚动重置/升级发放。"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.models  # noqa: F401  触发全部 mapper 注册（含 CreditLog）
from app.services.quota_service import QuotaService


@pytest.mark.asyncio
async def test_free_quota_seeds_credits(db_session):
    svc = QuotaService(db_session)
    q = await svc.get_or_create_quota(1)
    assert q.credit_balance == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS
    assert q.monthly_credit_grant == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS
    assert q.credit_reset_at is not None


@pytest.mark.asyncio
async def test_consume_and_insufficient(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(2)  # 60 积分
    q = await svc.consume_credits(2, 50, reason="generate", ref_key="t1")
    assert q.credit_balance == 10
    with pytest.raises(HTTPException) as ei:
        await svc.consume_credits(2, 20, reason="generate", ref_key="t2")
    assert ei.value.status_code == 402
    # 失败不扣
    assert (await svc.get_or_create_quota(2)).credit_balance == 10


@pytest.mark.asyncio
async def test_consume_idempotent_by_ref(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(3)
    await svc.consume_credits(3, 10, reason="generate", ref_key="dup")
    await svc.consume_credits(3, 10, reason="generate", ref_key="dup")  # 同 ref 不重复扣
    assert (await svc.get_or_create_quota(3)).credit_balance == 50


@pytest.mark.asyncio
async def test_refund_idempotent(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(4)
    await svc.consume_credits(4, 30, reason="generate", ref_key="task4")  # 余额 30
    await svc.refund_credits(4, 30, ref_key="task4")
    await svc.refund_credits(4, 30, ref_key="task4")  # 幂等：只退一次
    assert (await svc.get_or_create_quota(4)).credit_balance == 60


@pytest.mark.asyncio
async def test_credit_reset_after_30_days(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(5)
    await svc.consume_credits(5, 50, ref_key="x")  # 余额 10
    q = await svc.get_or_create_quota(5)
    q.credit_reset_at = datetime.utcnow() - timedelta(days=31)
    await db_session.commit()
    q = await svc.check_and_reset_credit(q)
    assert q.credit_balance == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS  # 默认不累积→重置为额度


@pytest.mark.asyncio
async def test_upgrade_grants_tier_credits(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(6)
    plan = SimpleNamespace(tier="flagship", daily_chapter_limit=0, monthly_credits=0, name="旗舰版")
    q = await svc.upgrade_to_premium(6, expires_at=None, plan=plan)
    assert q.plan_tier == "flagship"
    assert q.credit_balance == QuotaService.DEFAULT_FLAGSHIP_MONTHLY_CREDITS
    # 套餐显式 monthly_credits 优先
    plan2 = SimpleNamespace(tier="creator", daily_chapter_limit=0, monthly_credits=500, name="创作者版")
    q2 = await svc.upgrade_to_premium(7, expires_at=None, plan=plan2)
    assert q2.credit_balance == 500


@pytest.mark.asyncio
async def test_existing_user_credit_init(db_session):
    """既有用户(列回填 grant=0/balance=0/reset_at=None)首次接触积分体系 → 按档位初始化，
    避免激活计费后老用户被 402 卡死。"""
    from app.models.user_quota import UserQuota
    svc = QuotaService(db_session)
    q = UserQuota(user_id=99, credit_balance=0, monthly_credit_grant=0, credit_reset_at=None)
    db_session.add(q)
    await db_session.commit()
    q = await svc.check_and_reset_credit(q)
    assert q.monthly_credit_grant == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS
    assert q.credit_balance == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS

    q2 = UserQuota(user_id=98, is_premium=True, plan_tier="flagship",
                   credit_balance=0, monthly_credit_grant=0, credit_reset_at=None)
    db_session.add(q2)
    await db_session.commit()
    q2 = await svc.check_and_reset_credit(q2)
    assert q2.credit_balance == QuotaService.DEFAULT_FLAGSHIP_MONTHLY_CREDITS


@pytest.mark.asyncio
async def test_quota_info_has_credit_block(db_session):
    svc = QuotaService(db_session)
    info = await svc.get_quota_info(8)
    assert "credit" in info
    assert info["credit"]["balance"] == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS
    assert info["credit"]["reset_at"] is not None
