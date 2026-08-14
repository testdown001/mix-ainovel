"""邀请返积分回归。

钉住的契约：
- 邀请码自校验（HMAC 签名），篡改 user_id 必被拒——码里带明文 id，签名是唯一防线；
- 双方奖励入永久池且幂等（重放注册回调不重复发放）；
- 上限只限制邀请人：超限后受邀人照发（对新用户守信），邀请人不再得（防刷）；
- 无效码/自邀/关闭开关一律静默 no-op，绝不影响注册。
"""
from datetime import datetime

import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
from app.models.credit_log import CreditLog
from app.models.system_config import SystemConfig
from app.models.user import User
from app.models.user_quota import UserQuota
from app.services import referral_service as rs


async def _mk_user(db, uid, active=True):
    db.add(User(id=uid, username=f"u{uid}", email=f"u{uid}@example.com", hashed_password="x", is_active=active))
    await db.commit()


async def _quota(db, uid) -> UserQuota:
    from sqlalchemy import select

    return (await db.execute(select(UserQuota).where(UserQuota.user_id == uid))).scalars().first()


async def _set_config(db, key, value):
    db.add(SystemConfig(key=key, value=value))
    await db.commit()


def test_invite_code_roundtrip_and_tamper_rejection():
    code = rs.build_invite_code(42)
    assert rs.parse_invite_code(code) == 42
    # 篡改 id：签名对不上
    forged = "43-" + code.split("-")[1]
    assert rs.parse_invite_code(forged) is None
    assert rs.parse_invite_code("not-a-code") is None
    assert rs.parse_invite_code("") is None
    assert rs.parse_invite_code(None) is None
    assert rs.parse_invite_code("0-abcdefgh") is None


@pytest.mark.asyncio
async def test_rewards_both_sides_into_purchased_pool(db_session):
    await _mk_user(db_session, 1)
    await _mk_user(db_session, 2)

    granted = await rs.grant_referral_rewards(
        db_session, new_user_id=2, invite_code=rs.build_invite_code(1)
    )
    assert granted is True

    inviter = await _quota(db_session, 1)
    invitee = await _quota(db_session, 2)
    # 入永久池：月度池默认到期清零，注册奖励下月蒸发会被视为欺诈。
    # （月度池 credit_balance 由建档时的档位初始额度决定，与邀请无关，不在此断言）
    assert inviter.credit_purchased == rs.DEFAULT_INVITER_CREDITS
    assert invitee.credit_purchased == rs.DEFAULT_INVITEE_CREDITS

    from sqlalchemy import select

    rows = (await db_session.execute(
        select(CreditLog).where(CreditLog.reason == "referral").order_by(CreditLog.user_id)
    )).scalars().all()
    assert [(r.user_id, r.delta, r.ref_key) for r in rows] == [
        (1, rs.DEFAULT_INVITER_CREDITS, "inviter-of:2"),
        (2, rs.DEFAULT_INVITEE_CREDITS, "invitee:2"),
    ]


@pytest.mark.asyncio
async def test_replay_is_idempotent(db_session):
    await _mk_user(db_session, 1)
    await _mk_user(db_session, 2)
    code = rs.build_invite_code(1)

    await rs.grant_referral_rewards(db_session, new_user_id=2, invite_code=code)
    await rs.grant_referral_rewards(db_session, new_user_id=2, invite_code=code)

    inviter = await _quota(db_session, 1)
    invitee = await _quota(db_session, 2)
    assert inviter.credit_purchased == rs.DEFAULT_INVITER_CREDITS
    assert invitee.credit_purchased == rs.DEFAULT_INVITEE_CREDITS


@pytest.mark.asyncio
async def test_cap_limits_inviter_but_not_invitee(db_session):
    await _mk_user(db_session, 1)
    await _set_config(db_session, "referral.max_invites", "1")
    await _mk_user(db_session, 2)
    await _mk_user(db_session, 3)
    code = rs.build_invite_code(1)

    await rs.grant_referral_rewards(db_session, new_user_id=2, invite_code=code)
    await rs.grant_referral_rewards(db_session, new_user_id=3, invite_code=code)

    inviter = await _quota(db_session, 1)
    third = await _quota(db_session, 3)
    # 邀请人只得第一笔；第二位受邀人照常得
    assert inviter.credit_purchased == rs.DEFAULT_INVITER_CREDITS
    assert third.credit_purchased == rs.DEFAULT_INVITEE_CREDITS


@pytest.mark.asyncio
async def test_disabled_switch_noop(db_session):
    await _mk_user(db_session, 1)
    await _mk_user(db_session, 2)
    await _set_config(db_session, "referral.enabled", "false")

    granted = await rs.grant_referral_rewards(
        db_session, new_user_id=2, invite_code=rs.build_invite_code(1)
    )
    assert granted is False
    assert await _quota(db_session, 2) is None  # 连配额行都不该被创建


@pytest.mark.asyncio
async def test_invalid_code_and_self_invite_noop(db_session):
    await _mk_user(db_session, 1)
    assert await rs.grant_referral_rewards(db_session, new_user_id=1, invite_code=rs.build_invite_code(1)) is False
    assert await rs.grant_referral_rewards(db_session, new_user_id=1, invite_code="1-deadbeef") is False
    assert await rs.grant_referral_rewards(db_session, new_user_id=1, invite_code=None) is False
    # 邀请人不存在
    assert await rs.grant_referral_rewards(db_session, new_user_id=1, invite_code=rs.build_invite_code(999)) is False


@pytest.mark.asyncio
async def test_inactive_inviter_rejected(db_session):
    await _mk_user(db_session, 1, active=False)
    await _mk_user(db_session, 2)
    granted = await rs.grant_referral_rewards(
        db_session, new_user_id=2, invite_code=rs.build_invite_code(1)
    )
    assert granted is False


@pytest.mark.asyncio
async def test_referral_info_stats(db_session):
    await _mk_user(db_session, 1)
    await _mk_user(db_session, 2)
    await _mk_user(db_session, 3)
    code = rs.build_invite_code(1)
    await rs.grant_referral_rewards(db_session, new_user_id=2, invite_code=code)
    await rs.grant_referral_rewards(db_session, new_user_id=3, invite_code=code)

    info = await rs.get_referral_info(db_session, 1)
    assert info["invite_code"] == code
    assert info["invited_count"] == 2
    assert info["credits_earned"] == rs.DEFAULT_INVITER_CREDITS * 2
    assert info["enabled"] is True

    # 没邀请过的人：统计为零，码照常给
    info_empty = await rs.get_referral_info(db_session, 3)
    assert info_empty["invited_count"] == 0
    assert info_empty["credits_earned"] == 0
