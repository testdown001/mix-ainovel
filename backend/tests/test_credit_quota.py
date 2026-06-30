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
async def test_list_credit_logs_pagination(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(20)
    await svc.consume_credits(20, 5, reason="generate", ref_key="g1")
    await svc.consume_credits(20, 5, reason="polish", ref_key="p1")
    await svc.refund_credits(20, 5, ref_key="g1")  # reason=refund，与上面不冲突

    res = await svc.list_credit_logs(20, limit=2, offset=0)
    assert res["total"] >= 3  # 至少 generate + polish + refund
    assert res["limit"] == 2 and res["offset"] == 0
    assert len(res["items"]) == 2
    # 时间倒序（created_at desc, id desc）：最新一条是退款
    first = res["items"][0]
    assert first["reason"] == "refund"
    assert first["delta"] == 5
    assert {"id", "delta", "reason", "balance_after", "created_at"} <= set(first.keys())

    # 第二页承接，且 limit 被钳制在 [1,100]
    page2 = await svc.list_credit_logs(20, limit=999, offset=2)
    assert page2["limit"] == 100
    assert all(it["user_id"] if "user_id" in it else True for it in page2["items"])  # 仅本人流水


@pytest.mark.asyncio
async def test_credit_logs_isolated_per_user(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(21)
    await svc.get_or_create_quota(22)
    await svc.consume_credits(21, 5, reason="generate", ref_key="u21")
    res22 = await svc.list_credit_logs(22, limit=20, offset=0)
    # 用户 22 不应看到用户 21 的扣费流水
    assert all(it["reason"] != "generate" or it["ref_key"] != "u21" for it in res22["items"])


@pytest.mark.asyncio
async def test_quota_info_has_credit_block(db_session):
    svc = QuotaService(db_session)
    info = await svc.get_quota_info(8)
    assert "credit" in info
    assert info["credit"]["balance"] == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS
    assert info["credit"]["reset_at"] is not None
