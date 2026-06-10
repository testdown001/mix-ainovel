"""测试用户档位信息在认证流程中的集成"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.user_quota import UserQuota
from app.repositories.user_repository import UserRepository
from app.services.quota_service import QuotaService
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.schemas.user import UserInDB
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_current_user_includes_tier_info(db_session: AsyncSession):
    """测试 get_current_user 返回包含档位信息的用户"""
    # 创建测试用户
    user_repo = UserRepository(db_session)
    user = User(
        username="tier_test_user",
        email="tier@test.com",
        hashed_password="dummy_hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 创建 quota（创作者档位，订阅有效——effective_tier 仅在 Premium 生效时返回 plan_tier）
    from datetime import datetime, timedelta

    quota = UserQuota(
        user_id=user.id,
        plan_tier="creator",
        is_premium=True,
        premium_expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db_session.add(quota)
    await db_session.commit()

    # 生成 token
    token = create_access_token(str(user.id))

    # 调用 get_current_user
    result = await get_current_user(token=token, session=db_session)

    # 验证返回的用户包含档位信息
    assert isinstance(result, UserInDB)
    assert result.id == user.id
    assert result.username == "tier_test_user"
    assert result.plan_tier == "creator"
    assert result.effective_tier == "creator"


@pytest.mark.asyncio
async def test_current_user_free_tier_when_no_quota(db_session: AsyncSession):
    """测试没有 quota 记录时默认为 free 档位"""
    # 创建测试用户（不创建 quota）
    user_repo = UserRepository(db_session)
    user = User(
        username="no_quota_user",
        email="noquota@test.com",
        hashed_password="dummy_hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 生成 token
    token = create_access_token(str(user.id))

    # 调用 get_current_user
    result = await get_current_user(token=token, session=db_session)

    # 验证默认为 free 档位
    assert result.plan_tier == "free"
    assert result.effective_tier == "free"


@pytest.mark.asyncio
async def test_current_user_effective_tier_fallback(db_session: AsyncSession):
    """测试 effective_tier 的回退逻辑（Premium 失效）"""
    # 创建测试用户
    user = User(
        username="fallback_user",
        email="fallback@test.com",
        hashed_password="dummy_hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 创建已过期的 Premium quota
    from datetime import datetime, timedelta
    quota = UserQuota(
        user_id=user.id,
        plan_tier="flagship",
        is_premium=True,
        premium_expires_at=datetime.utcnow() - timedelta(days=1),  # 已过期
    )
    db_session.add(quota)
    await db_session.commit()

    # 生成 token
    token = create_access_token(str(user.id))

    # 调用 get_current_user
    result = await get_current_user(token=token, session=db_session)

    # 验证 effective_tier 回退到 free（Premium 已过期）
    assert result.plan_tier == "flagship"
    assert result.effective_tier == "free"  # 过期回退
