"""会员到期邮件提醒回归:

- 候选筛选:仅临期(窗口内、未过期)会员;免费/已过期/窗口外不入选
- 幂等:同一到期时间只提醒一次;续费(到期时间变化)后重新可提醒
- 认领:_claim 原子 compare-and-set,重复认领失败(多副本防重)
- sweep:开关关闭 / 无临期用户 → no-op;发信统计正确(邮件通道打桩)
"""
from datetime import datetime, timedelta

import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
from app.models.system_config import SystemConfig
from app.models.user import User
from app.models.user_quota import UserQuota
from app.services import subscription_reminder_service as srs


_UNSET = object()


async def _mk_user(db, uid, email=_UNSET, is_active=True):
    # 每个用户默认唯一邮箱(users.email 有唯一约束);显式传 None 表示无邮箱
    if email is _UNSET:
        email = f"u{uid}@example.com"
    db.add(User(id=uid, username=f"u{uid}", email=email, hashed_password="x", is_active=is_active))
    await db.commit()


async def _mk_quota(db, uid, *, is_premium=True, tier="creator", expires_in_days=2, reminded_for=None):
    q = UserQuota(
        user_id=uid,
        is_premium=is_premium,
        plan_tier=tier,
        premium_expires_at=(datetime.utcnow() + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
        expiry_reminded_for=reminded_for,
    )
    db.add(q)
    await db.commit()
    return q


@pytest.mark.asyncio
async def test_candidates_only_expiring_premium(db_session):
    await _mk_user(db_session, 1)
    await _mk_user(db_session, 2)
    await _mk_user(db_session, 3)
    await _mk_user(db_session, 4)
    await _mk_quota(db_session, 1, is_premium=True, expires_in_days=2)     # ✓ 临期
    await _mk_quota(db_session, 2, is_premium=True, expires_in_days=10)    # ✗ 窗口外
    await _mk_quota(db_session, 3, is_premium=False, expires_in_days=2)    # ✗ 非会员
    await _mk_quota(db_session, 4, is_premium=True, expires_in_days=-1)    # ✗ 已过期

    cands = await srs.find_reminder_candidates(db_session, within_days=3)
    assert {c.user_id for c in cands} == {1}


@pytest.mark.asyncio
async def test_idempotent_anchor_excludes_already_reminded(db_session):
    await _mk_user(db_session, 5)
    q = await _mk_quota(db_session, 5, expires_in_days=2)
    # 标记已针对当前到期时间提醒过
    q.expiry_reminded_for = q.premium_expires_at
    await db_session.commit()

    cands = await srs.find_reminder_candidates(db_session, within_days=3)
    assert all(c.user_id != 5 for c in cands)


@pytest.mark.asyncio
async def test_renewal_makes_eligible_again(db_session):
    await _mk_user(db_session, 6)
    q = await _mk_quota(db_session, 6, expires_in_days=2)
    q.expiry_reminded_for = datetime.utcnow() - timedelta(days=90)  # 上个周期提醒过
    await db_session.commit()
    # 当前到期时间 != 旧锚 → 重新可提醒
    cands = await srs.find_reminder_candidates(db_session, within_days=3)
    assert any(c.user_id == 6 for c in cands)


@pytest.mark.asyncio
async def test_claim_is_atomic_once(db_session):
    await _mk_user(db_session, 7)
    q = await _mk_quota(db_session, 7, expires_in_days=2)
    assert await srs._claim(db_session, q) is True
    # 第二次认领(模拟另一副本):锚已置为当前到期时间 → 失败
    q2 = await db_session.get(UserQuota, q.id)
    assert await srs._claim(db_session, q2) is False


@pytest.mark.asyncio
async def test_sweep_disabled_noop(db_session):
    db_session.add(SystemConfig(key="subscription.reminder_enabled", value="false"))
    await _mk_user(db_session, 8)
    await _mk_quota(db_session, 8, expires_in_days=1)
    await db_session.commit()
    result = await srs.run_reminder_sweep(db_session)
    assert result == {"enabled": False, "candidates": 0, "sent": 0, "skipped": 0}


@pytest.mark.asyncio
async def test_sweep_sends_and_stamps(db_session, monkeypatch):
    await _mk_user(db_session, 9, email="reader@example.com")
    q = await _mk_quota(db_session, 9, tier="flagship", expires_in_days=1)

    sent_to = []

    async def fake_send(self, to_email, subject, html):  # noqa: ANN001
        sent_to.append((to_email, subject))
        return True

    monkeypatch.setattr("app.services.auth_service.AuthService.send_html_email", fake_send)

    result = await srs.run_reminder_sweep(db_session)
    assert result["enabled"] is True
    assert result["candidates"] == 1
    assert result["sent"] == 1
    assert sent_to and sent_to[0][0] == "reader@example.com"

    # 幂等:再扫一次不再发
    result2 = await srs.run_reminder_sweep(db_session)
    assert result2["sent"] == 0

    refreshed = await db_session.get(UserQuota, q.id)
    assert refreshed.expiry_reminded_for == refreshed.premium_expires_at


@pytest.mark.asyncio
async def test_sweep_skips_user_without_email(db_session, monkeypatch):
    await _mk_user(db_session, 10, email=None)
    await _mk_quota(db_session, 10, expires_in_days=1)

    async def fake_send(self, to_email, subject, html):  # noqa: ANN001
        raise AssertionError("无邮箱用户不应触发发送")

    monkeypatch.setattr("app.services.auth_service.AuthService.send_html_email", fake_send)
    result = await srs.run_reminder_sweep(db_session)
    assert result["sent"] == 0
    assert result["skipped"] == 1
