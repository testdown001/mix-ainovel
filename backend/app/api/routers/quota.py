# AIMETA P=配额API_用户配额查询|R=配额查询_配额管理|E=route:GET_/api/quota/*|X=http|A=配额接口|D=fastapi|S=net
"""
用户配额 API Router - 配额查询和管理

核心功能：
1. 查询用户配额信息
2. 管理员配额管理
"""
import logging
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user, get_current_admin
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.quota_service import QuotaService

router = APIRouter(prefix="/api/quota", tags=["Quota"])
logger = logging.getLogger(__name__)


@router.get("/me", response_model=Dict)
async def get_my_quota(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """
    获取当前用户配额信息

    返回：
    - 每日章节生成配额
    - 存储空间配额
    - 每月 token 配额
    - Premium 状态
    """
    quota_service = QuotaService(session)
    return await quota_service.get_quota_info(current_user.id)


@router.get("/me/referral", response_model=Dict)
async def get_my_referral(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """「邀请返积分」面板：我的邀请码、奖励规则、已邀请人数与已得积分。"""
    from ...services.referral_service import get_referral_info

    return await get_referral_info(session, current_user.id)


@router.get("/me/credit-logs", response_model=Dict)
async def get_my_credit_logs(
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict:
    """获取当前用户的积分流水（分页，时间倒序）。

    Args:
        limit: 每页条数（1-100，默认 20）
        offset: 偏移量（默认 0）
    """
    quota_service = QuotaService(session)
    return await quota_service.list_credit_logs(current_user.id, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=Dict)
async def get_user_quota(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> Dict:
    """
    获取指定用户配额信息（管理员）

    Args:
        user_id: 用户 ID
    """
    quota_service = QuotaService(session)
    return await quota_service.get_quota_info(user_id)


@router.post("/{user_id}/upgrade-premium")
async def upgrade_user_to_premium(
    user_id: int,
    days: int = 30,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> Dict:
    """
    升级用户为 Premium（管理员）

    Args:
        user_id: 用户 ID
        days: Premium 有效天数（默认 30 天）
    """
    from datetime import datetime, timedelta

    quota_service = QuotaService(session)
    expires_at = datetime.utcnow() + timedelta(days=days)
    quota = await quota_service.upgrade_to_premium(user_id, expires_at)

    return {
        "user_id": user_id,
        "is_premium": True,
        "premium_expires_at": quota.premium_expires_at.isoformat(),
        "message": f"用户已升级为 Premium，有效期 {days} 天",
    }


@router.post("/{user_id}/downgrade-premium")
async def downgrade_user_from_premium(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> Dict:
    """
    降级用户为普通用户（管理员）

    Args:
        user_id: 用户 ID
    """
    quota_service = QuotaService(session)
    await quota_service.downgrade_from_premium(user_id)

    return {
        "user_id": user_id,
        "is_premium": False,
        "message": "用户已降级为普通用户",
    }


@router.post("/{user_id}/reset-daily")
async def reset_user_daily_quota(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_admin),
) -> Dict:
    """
    重置用户每日配额（管理员）

    Args:
        user_id: 用户 ID
    """
    quota_service = QuotaService(session)
    quota = await quota_service.get_or_create_quota(user_id)
    quota.daily_chapter_used = 0
    await session.commit()

    return {
        "user_id": user_id,
        "message": "每日配额已重置",
    }
