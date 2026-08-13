# AIMETA P=会员到期邮件提醒_扫描临期会员并召回|R=find/claim/send 到期提醒|E=run_reminder_sweep|X=internal|A=服务函数|D=sqlalchemy|S=db,net
"""会员到期邮件提醒。

与「到期横幅」(RenewalBanner,登录后可见)互补:横幅召回活跃用户,邮件召回已离开的用户。
设计:
- 幂等锚 UserQuota.expiry_reminded_for = 已提醒过的那个到期时间;续费后 premium_expires_at
  变化即重新可提醒。
- 多副本安全:先条件 UPDATE 认领(原子 compare-and-set),rowcount==1 才发信,天然互斥。
- 至多一次:先认领后发信,发信失败仅记日志(宁可漏提醒不重复打扰)。
- SystemConfig 开关:subscription.reminder_enabled(默认 true)/ reminder_days(默认 3)。
- 邮件未配置或无临期用户时静默 no-op,绝不影响主流程。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..models.user_quota import UserQuota
from ..repositories.system_config_repository import SystemConfigRepository

logger = logging.getLogger(__name__)

DEFAULT_REMINDER_DAYS = 3


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def build_reminder_email_html(*, tier_label: str, expires_at: datetime, days_left: int) -> str:
    day_text = "今天" if days_left <= 0 else f"{days_left} 天后"
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f3f4f6;">
  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f3f4f6"><tr>
    <td align="center" style="padding:20px;">
      <table cellpadding="0" cellspacing="0" width="100%" style="max-width:512px;background:#ffffff;border-radius:16px;overflow:hidden;">
        <tr><td align="center" style="background:#111111;padding:32px;">
          <h1 style="font-family:Arial,sans-serif;font-size:24px;font-weight:bold;color:#FFE500;margin:0;">会员即将到期</h1>
        </td></tr>
        <tr><td style="padding:32px 40px;font-family:Arial,'Microsoft YaHei',sans-serif;color:#374151;">
          <p style="font-size:16px;line-height:1.7;margin:0 0 16px;">
            你的 <strong>{tier_label}</strong> 将于 <strong>{day_text}</strong>({expires_at.strftime('%Y-%m-%d')})到期。
          </p>
          <p style="font-size:14px;line-height:1.7;color:#6b7280;margin:0 0 24px;">
            到期后将自动降为免费版,每月积分额度与档位能力(稳定连载/关键章节精修等)会同步回落。
            续费即可无缝继续你的创作,已写内容与项目数据永久保留。
          </p>
          <p style="font-size:13px;line-height:1.7;color:#9ca3af;margin:0;">
            登录后进入「设置 → 会员套餐」即可续费。若已续费请忽略本邮件。
          </p>
        </td></tr>
        <tr><td align="center" style="background:#f9fafb;padding:20px;border-top:1px solid #e5e7eb;">
          <p style="font-family:Arial,sans-serif;font-size:12px;color:#9ca3af;margin:0;">
            &copy; {datetime.utcnow().year} 章鱼 AI 写作
          </p>
        </td></tr>
      </table>
    </td></tr></table>
</body></html>
"""


async def _reminder_config(session: AsyncSession) -> tuple[bool, int]:
    raw = await SystemConfigRepository(session).get_many(
        ["subscription.reminder_enabled", "subscription.reminder_days"]
    )
    enabled = _parse_bool(raw.get("subscription.reminder_enabled"), True)
    try:
        days = max(1, int(raw.get("subscription.reminder_days", DEFAULT_REMINDER_DAYS)))
    except (TypeError, ValueError):
        days = DEFAULT_REMINDER_DAYS
    return enabled, days


async def find_reminder_candidates(session: AsyncSession, *, within_days: int, now: Optional[datetime] = None):
    """临期且尚未针对当前到期时间提醒过的会员配额。"""
    now = now or datetime.utcnow()
    horizon = now + timedelta(days=within_days)
    stmt = (
        select(UserQuota)
        .where(
            UserQuota.is_premium == True,  # noqa: E712
            UserQuota.premium_expires_at.is_not(None),
            UserQuota.premium_expires_at > now,
            UserQuota.premium_expires_at <= horizon,
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    # 幂等锚在 Python 侧比较(跨 mysql/sqlite 对 NULL != 值 的行为一致)
    return [
        q for q in rows
        if q.expiry_reminded_for is None or q.expiry_reminded_for != q.premium_expires_at
    ]


async def _claim(session: AsyncSession, quota: UserQuota) -> bool:
    """原子认领:把 expiry_reminded_for 置为当前到期时间,仅当尚未认领。rowcount==1 即认领成功。
    多副本并发下只有一个能认领成功,天然防重复发信。"""
    result = await session.execute(
        update(UserQuota)
        .where(
            UserQuota.id == quota.id,
            UserQuota.premium_expires_at == quota.premium_expires_at,
            (UserQuota.expiry_reminded_for.is_(None))
            | (UserQuota.expiry_reminded_for != quota.premium_expires_at),
        )
        .values(expiry_reminded_for=quota.premium_expires_at)
    )
    await session.commit()
    return (result.rowcount or 0) == 1


async def run_reminder_sweep(session: AsyncSession, *, now: Optional[datetime] = None) -> dict:
    """执行一次到期提醒扫描。返回 {enabled, candidates, sent, skipped}。"""
    from .auth_service import AuthService  # 延迟导入避免循环依赖

    now = now or datetime.utcnow()
    enabled, days = await _reminder_config(session)
    if not enabled:
        return {"enabled": False, "candidates": 0, "sent": 0, "skipped": 0}

    candidates = await find_reminder_candidates(session, within_days=days, now=now)
    if not candidates:
        return {"enabled": True, "candidates": 0, "sent": 0, "skipped": 0}

    auth_service = AuthService(session)
    sent = 0
    skipped = 0
    for quota in candidates:
        user = await session.get(User, quota.user_id)
        if not user or not getattr(user, "is_active", True) or not getattr(user, "email", None):
            skipped += 1
            continue
        # 先认领(原子),认领失败说明其它副本已处理
        expires_at = quota.premium_expires_at
        if not await _claim(session, quota):
            skipped += 1
            continue
        days_left = max(0, (expires_at - now).days)
        tier_label = "旗舰版会员" if (quota.plan_tier or "") == "flagship" else "创作者版会员"
        html = build_reminder_email_html(tier_label=tier_label, expires_at=expires_at, days_left=days_left)
        try:
            ok = await auth_service.send_html_email(user.email, "你的会员即将到期", html)
            if ok:
                sent += 1
                logger.info("会员到期提醒已发送: user_id=%s expires=%s", quota.user_id, expires_at)
            else:
                skipped += 1  # 邮件通道未配置
        except Exception:
            skipped += 1
            logger.warning("会员到期提醒发送失败: user_id=%s", quota.user_id, exc_info=True)
    return {"enabled": True, "candidates": len(candidates), "sent": sent, "skipped": skipped}
