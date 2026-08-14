# AIMETA P=邀请返积分_签名邀请码与奖励发放|R=邀请码生成校验_双方奖励_统计|NR=不含注册流程|E=ReferralService|X=internal|A=服务函数|D=sqlalchemy|S=db|RD=./README.ai
"""邀请返积分。

设计取舍：
- 邀请码 = "{user_id}-{HMAC(secret, user_id) 前 8 位}"，**零表结构变更**——不加列、
  不发码表。码可自校验（篡改 user_id 必然过不了签名），用 settings.secret_key 做密钥。
- 邀请关系不单独建表：奖励本身就是记录。每次成功邀请产生两条 CreditLog
  （reason='referral'）：受邀人 ref_key='invitee:{新用户id}'，邀请人
  ref_key='inviter-of:{新用户id}'——(reason, ref_key) 唯一约束天然幂等，
  统计「我邀请了几人/赚了多少」就是数邀请人自己的 referral 流水。
- 奖励入**永久池**（add_purchased_credits）：月度池默认到期清零，注册奖励下月就
  蒸发会被用户视为欺诈。防滥用靠 referral.max_invites 上限（超限后受邀人照发、
  邀请人不再得），金额与开关都在 SystemConfig，后台可随时调。
- 发放失败绝不阻断注册（调用方负责 try/except），幂等使重试安全。
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.credit_log import CreditLog
from ..models.user import User

logger = logging.getLogger(__name__)

_REASON = "referral"
_INVITER_PREFIX = "inviter-of:"
_INVITEE_PREFIX = "invitee:"

DEFAULT_INVITER_CREDITS = 30
DEFAULT_INVITEE_CREDITS = 20
DEFAULT_MAX_INVITES = 50


def build_invite_code(user_id: int) -> str:
    """用户的邀请码（确定性，可随时重算，无需存储）。"""
    return f"{user_id}-{_sign(user_id)}"


def parse_invite_code(code: Optional[str]) -> Optional[int]:
    """校验并解出邀请人 user_id；格式错误或签名不符返回 None。"""
    if not code:
        return None
    parts = code.strip().split("-", 1)
    if len(parts) != 2 or not parts[0].isdigit():
        return None
    user_id = int(parts[0])
    if user_id <= 0:
        return None
    if not hmac.compare_digest(parts[1], _sign(user_id)):
        return None
    return user_id


def _sign(user_id: int) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"referral:{user_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:8]


async def _load_config(session: AsyncSession) -> Dict[str, int]:
    from ..repositories.system_config_repository import SystemConfigRepository

    raw = await SystemConfigRepository(session).get_many(
        ["referral.enabled", "referral.inviter_credits", "referral.invitee_credits", "referral.max_invites"]
    )
    enabled = str(raw.get("referral.enabled", "true")).strip().lower() in ("1", "true", "yes", "on")

    def _int(key: str, default: int) -> int:
        try:
            return max(0, int(raw.get(key, default)))
        except (TypeError, ValueError):
            return default

    return {
        "enabled": int(enabled),
        "inviter_credits": _int("referral.inviter_credits", DEFAULT_INVITER_CREDITS),
        "invitee_credits": _int("referral.invitee_credits", DEFAULT_INVITEE_CREDITS),
        "max_invites": _int("referral.max_invites", DEFAULT_MAX_INVITES),
    }


async def _inviter_reward_count(session: AsyncSession, inviter_id: int) -> int:
    result = await session.execute(
        select(func.count(CreditLog.id)).where(
            CreditLog.user_id == inviter_id,
            CreditLog.reason == _REASON,
            CreditLog.ref_key.like(f"{_INVITER_PREFIX}%"),
        )
    )
    return int(result.scalar() or 0)


async def grant_referral_rewards(session: AsyncSession, *, new_user_id: int, invite_code: Optional[str]) -> bool:
    """注册成功后发放邀请奖励；返回是否发放了受邀人奖励。

    无效码/自邀/功能关闭一律静默 no-op——邀请是增益，任何分支都不该让注册变糟。
    """
    inviter_id = parse_invite_code(invite_code)
    if inviter_id is None or inviter_id == new_user_id:
        return False

    inviter = await session.get(User, inviter_id)
    if inviter is None or not inviter.is_active:
        return False

    config = await _load_config(session)
    if not config["enabled"]:
        return False

    from .quota_service import QuotaService

    quota_service = QuotaService(session)
    granted = False

    if config["invitee_credits"] > 0:
        await quota_service.add_purchased_credits(
            new_user_id,
            config["invitee_credits"],
            ref_key=f"{_INVITEE_PREFIX}{new_user_id}",
            note=f"受邀注册奖励（邀请人 #{inviter_id}）",
            reason=_REASON,
        )
        granted = True

    # 邀请人奖励设上限：超限后受邀人照发（对新用户守信），邀请人不再得（防刷）
    if config["inviter_credits"] > 0:
        rewarded = await _inviter_reward_count(session, inviter_id)
        if rewarded < config["max_invites"]:
            await quota_service.add_purchased_credits(
                inviter_id,
                config["inviter_credits"],
                ref_key=f"{_INVITER_PREFIX}{new_user_id}",
                note=f"邀请新用户 #{new_user_id} 注册",
                reason=_REASON,
            )
        else:
            logger.info("邀请奖励达上限，跳过邀请人发放: inviter=%s cap=%s", inviter_id, config["max_invites"])

    if granted:
        logger.info("邀请奖励发放: inviter=%s invitee=%s", inviter_id, new_user_id)
    return granted


async def get_referral_info(session: AsyncSession, user_id: int) -> Dict[str, Any]:
    """「邀请返积分」面板数据：我的码 + 奖励规则 + 已邀统计。"""
    config = await _load_config(session)
    stats = await session.execute(
        select(func.count(CreditLog.id), func.coalesce(func.sum(CreditLog.delta), 0)).where(
            CreditLog.user_id == user_id,
            CreditLog.reason == _REASON,
            CreditLog.ref_key.like(f"{_INVITER_PREFIX}%"),
        )
    )
    invited_count, credits_earned = stats.one()
    return {
        "enabled": bool(config["enabled"]),
        "invite_code": build_invite_code(user_id),
        "inviter_credits": config["inviter_credits"],
        "invitee_credits": config["invitee_credits"],
        "max_invites": config["max_invites"],
        "invited_count": int(invited_count or 0),
        "credits_earned": int(credits_earned or 0),
    }
