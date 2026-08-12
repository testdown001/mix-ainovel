"""注册试用发放（grant_signup_trial）回归：

定价页承诺「注册即享创作者版 3 天完整试用」——本组测试锁定：
1. 默认开启：新用户获得 3 天 creator + 一次性体验积分，且写入 trial 流水
2. 幂等：重复调用（OAuth 回调重放等）不重复发放
3. SystemConfig trial.enabled=false 可整体关闭
4. trial.days / trial.credits 可覆写
5. 已是会员（管理员手动授予等）不叠加
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.credit_log import CreditLog
from app.models.system_config import SystemConfig
from app.services.quota_service import QuotaService


@pytest.mark.asyncio
async def test_signup_trial_grants_creator_and_credits(db_session):
    svc = QuotaService(db_session)

    granted = await svc.grant_signup_trial(user_id=1)
    assert granted is True

    quota = await svc.get_quota(1)
    assert quota is not None
    assert quota.is_premium is True
    assert quota.plan_tier == "creator"
    assert quota.effective_tier == "creator"
    # 到期时间 ≈ 3 天后
    assert quota.premium_expires_at is not None
    delta = quota.premium_expires_at - datetime.utcnow()
    assert timedelta(days=2, hours=23) < delta <= timedelta(days=3, minutes=5)
    # 初始 free 发放 60 + 试用体验积分 300
    assert quota.credit_balance == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS + QuotaService.TRIAL_DEFAULT_CREDITS
    # 月度滚动发放额度保持 free 档（试用不改变滚动语义）
    assert quota.monthly_credit_grant == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS

    row = (
        await db_session.execute(
            select(CreditLog).where(CreditLog.reason == "trial", CreditLog.ref_key == "signup:1")
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.delta == QuotaService.TRIAL_DEFAULT_CREDITS
    assert row.balance_after == quota.credit_balance


@pytest.mark.asyncio
async def test_signup_trial_is_idempotent(db_session):
    svc = QuotaService(db_session)
    assert await svc.grant_signup_trial(user_id=2) is True
    quota = await svc.get_quota(2)
    balance_after_first = quota.credit_balance
    expires_after_first = quota.premium_expires_at

    # 试用到期后 effective_tier 回落 free，quota.is_premium 仍为 True 的窗口外，
    # 重放（如 OAuth 回调重试）也不能二次发放
    quota.is_premium = False
    await db_session.commit()

    assert await svc.grant_signup_trial(user_id=2) is False
    quota = await svc.get_quota(2)
    assert quota.credit_balance == balance_after_first
    assert quota.premium_expires_at == expires_after_first


@pytest.mark.asyncio
async def test_signup_trial_disabled_by_system_config(db_session):
    db_session.add(SystemConfig(key="trial.enabled", value="false"))
    await db_session.commit()

    svc = QuotaService(db_session)
    assert await svc.grant_signup_trial(user_id=3) is False
    quota = await svc.get_quota(3)
    # 未发放：不建 premium 状态（get_or_create 也未被触发到 premium 路径）
    assert quota is None or quota.is_premium is False


@pytest.mark.asyncio
async def test_signup_trial_config_overrides(db_session):
    db_session.add(SystemConfig(key="trial.days", value="7"))
    db_session.add(SystemConfig(key="trial.credits", value="500"))
    await db_session.commit()

    svc = QuotaService(db_session)
    assert await svc.grant_signup_trial(user_id=4) is True
    quota = await svc.get_quota(4)
    delta = quota.premium_expires_at - datetime.utcnow()
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7, minutes=5)
    assert quota.credit_balance == QuotaService.DEFAULT_FREE_MONTHLY_CREDITS + 500


@pytest.mark.asyncio
async def test_signup_trial_skips_existing_premium(db_session):
    svc = QuotaService(db_session)
    quota = await svc.get_or_create_quota(5)
    quota.is_premium = True
    quota.plan_tier = "flagship"
    await db_session.commit()

    assert await svc.grant_signup_trial(user_id=5) is False
    quota = await svc.get_quota(5)
    assert quota.plan_tier == "flagship"  # 不被试用覆盖
