# AIMETA P=配额服务_用户配额管理|R=配额检查_配额更新|E=QuotaService|X=internal|A=服务类|D=sqlalchemy|S=db
"""
用户配额服务 - 多租户资源管理

核心功能：
1. 配额检查和验证
2. 配额消耗和更新
3. 配额重置（每日/每月）
4. Premium 用户管理
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from ..models.user_quota import UserQuota

if TYPE_CHECKING:
    from ..models.plan import Plan

logger = logging.getLogger(__name__)


class QuotaService:
    """用户配额服务"""

    # 默认配额配置
    DEFAULT_DAILY_CHAPTER_LIMIT = 10
    DEFAULT_STORAGE_LIMIT = 1073741824  # 1GB
    DEFAULT_MONTHLY_TOKEN_LIMIT = 1000000  # 100 万 tokens

    # Premium 配额配置
    PREMIUM_DAILY_CHAPTER_LIMIT = 50
    PREMIUM_STORAGE_LIMIT = 10737418240  # 10GB
    PREMIUM_MONTHLY_TOKEN_LIMIT = 10000000  # 1000 万 tokens

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_quota(self, user_id: int) -> Optional[UserQuota]:
        """获取用户配额；不存在时返回 None，不创建记录。"""
        stmt = select(UserQuota).where(UserQuota.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_create_quota(self, user_id: int) -> UserQuota:
        """获取或创建用户配额"""
        quota = await self.get_quota(user_id)

        if not quota:
            quota = UserQuota(
                user_id=user_id,
                daily_chapter_limit=self.DEFAULT_DAILY_CHAPTER_LIMIT,
                storage_limit=self.DEFAULT_STORAGE_LIMIT,
                monthly_token_limit=self.DEFAULT_MONTHLY_TOKEN_LIMIT,
            )
            self.session.add(quota)
            await self.session.commit()
            await self.session.refresh(quota)
            logger.info(f"创建用户配额: user_id={user_id}")

        return quota

    async def check_and_reset_daily_quota(self, quota: UserQuota) -> UserQuota:
        """检查并重置每日配额"""
        now = datetime.utcnow()
        if now - quota.daily_reset_at >= timedelta(days=1):
            quota.daily_chapter_used = 0
            quota.daily_reset_at = now
            await self.session.commit()
            logger.info(f"重置每日配额: user_id={quota.user_id}")
        return quota

    async def check_and_reset_monthly_quota(self, quota: UserQuota) -> UserQuota:
        """检查并重置每月配额"""
        now = datetime.utcnow()
        if now - quota.monthly_reset_at >= timedelta(days=30):
            quota.monthly_token_used = 0
            quota.monthly_reset_at = now
            await self.session.commit()
            logger.info(f"重置每月配额: user_id={quota.user_id}")
        return quota

    async def check_chapter_quota(self, user_id: int) -> bool:
        """检查章节生成配额"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_daily_quota(quota)

        if not quota.can_generate_chapter:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日章节生成配额已用尽 ({quota.daily_chapter_used}/{quota.daily_chapter_limit})。"
                       f"{'升级到 Premium 可获得更多配额。' if not quota.is_premium_active else ''}",
            )
        return True

    async def consume_chapter_quota(self, user_id: int, count: int = 1) -> UserQuota:
        """消耗章节生成配额"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_daily_quota(quota)

        if quota.daily_chapter_used + count > quota.daily_chapter_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"章节生成配额不足。剩余: {quota.daily_chapter_limit - quota.daily_chapter_used}",
            )

        quota.daily_chapter_used += count
        quota.total_chapters_generated += count
        await self.session.commit()
        await self.session.refresh(quota)

        logger.info(
            f"消耗章节配额: user_id={user_id}, count={count}, "
            f"remaining={quota.daily_chapter_limit - quota.daily_chapter_used}"
        )
        return quota

    async def check_storage_quota(self, user_id: int, size: int) -> bool:
        """检查存储配额"""
        quota = await self.get_or_create_quota(user_id)

        if not quota.can_use_storage(size):
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail=f"存储空间不足。已使用: {quota.storage_used / 1024 / 1024:.2f}MB / "
                       f"{quota.storage_limit / 1024 / 1024:.2f}MB",
            )
        return True

    async def consume_storage_quota(self, user_id: int, size: int) -> UserQuota:
        """消耗存储配额"""
        quota = await self.get_or_create_quota(user_id)

        if quota.storage_used + size > quota.storage_limit:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail=f"存储空间不足",
            )

        quota.storage_used += size
        await self.session.commit()
        await self.session.refresh(quota)

        logger.info(f"消耗存储配额: user_id={user_id}, size={size} bytes")
        return quota

    async def check_token_quota(self, user_id: int, tokens: int) -> bool:
        """检查 token 配额"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_monthly_quota(quota)

        if not quota.can_use_tokens(tokens):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"本月 token 配额已用尽 ({quota.monthly_token_used}/{quota.monthly_token_limit})。",
            )
        return True

    async def consume_token_quota(self, user_id: int, tokens: int) -> UserQuota:
        """消耗 token 配额"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_monthly_quota(quota)

        if quota.monthly_token_used + tokens > quota.monthly_token_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Token 配额不足",
            )

        quota.monthly_token_used += tokens
        await self.session.commit()
        await self.session.refresh(quota)

        logger.info(f"消耗 token 配额: user_id={user_id}, tokens={tokens}")
        return quota

    @staticmethod
    def _derive_tier(plan: Optional["Plan"]) -> str:
        """从套餐推导订阅档位（free / creator / flagship）。

        优先使用后台显式配置的 plan.tier；缺失时回退按 plan.name 关键字猜测；
        无 plan 时按通用 premium 视作 creator。
        """
        name = (getattr(plan, "name", "") or "")
        explicit = (getattr(plan, "tier", "") or "").strip().lower()
        if explicit in ("creator", "flagship"):
            return explicit
        if "旗舰" in name or "flagship" in name.lower():
            return "flagship"
        if "创作者" in name or "creator" in name.lower():
            return "creator"
        if explicit == "free":
            try:
                price = float(getattr(plan, "price", 0) or 0)
            except (TypeError, ValueError):
                price = 0
            return "free" if price <= 0 else "creator"
        return "creator"  # 任意已付费套餐至少为 creator

    async def upgrade_to_premium(
        self,
        user_id: int,
        expires_at: Optional[datetime] = None,
        plan: Optional["Plan"] = None,
    ) -> UserQuota:
        """升级为 Premium 用户。

        若提供 plan 且其 daily_chapter_limit > 0，则采用套餐自定义的每日章节上限；
        否则回退到 PREMIUM 默认配额。storage/token 暂统一使用 PREMIUM 默认值。
        """
        quota = await self.get_or_create_quota(user_id)

        plan_daily = getattr(plan, "daily_chapter_limit", 0) or 0

        quota.is_premium = True
        quota.premium_expires_at = expires_at
        quota.plan_tier = self._derive_tier(plan)
        quota.daily_chapter_limit = plan_daily if plan_daily > 0 else self.PREMIUM_DAILY_CHAPTER_LIMIT
        quota.storage_limit = self.PREMIUM_STORAGE_LIMIT
        quota.monthly_token_limit = self.PREMIUM_MONTHLY_TOKEN_LIMIT

        await self.session.commit()
        await self.session.refresh(quota)

        logger.info(
            "升级为 Premium: user_id=%s, expires_at=%s, daily_limit=%s",
            user_id, expires_at, quota.daily_chapter_limit,
        )
        return quota

    async def downgrade_from_premium(self, user_id: int) -> UserQuota:
        """降级为普通用户"""
        quota = await self.get_or_create_quota(user_id)

        quota.is_premium = False
        quota.premium_expires_at = None
        quota.plan_tier = "free"
        quota.daily_chapter_limit = self.DEFAULT_DAILY_CHAPTER_LIMIT
        quota.storage_limit = self.DEFAULT_STORAGE_LIMIT
        quota.monthly_token_limit = self.DEFAULT_MONTHLY_TOKEN_LIMIT

        await self.session.commit()
        await self.session.refresh(quota)

        logger.info(f"降级为普通用户: user_id={user_id}")
        return quota

    async def get_quota_info(self, user_id: int) -> dict:
        """获取用户配额信息"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_daily_quota(quota)
        quota = await self.check_and_reset_monthly_quota(quota)

        return {
            "user_id": user_id,
            "is_premium": quota.is_premium_active,
            "plan_tier": quota.effective_tier,
            "premium_expires_at": quota.premium_expires_at.isoformat() if quota.premium_expires_at else None,
            "daily_chapter": {
                "used": quota.daily_chapter_used,
                "limit": quota.daily_chapter_limit,
                "remaining": quota.daily_chapter_limit - quota.daily_chapter_used,
            },
            "storage": {
                "used_mb": round(quota.storage_used / 1024 / 1024, 2),
                "limit_mb": round(quota.storage_limit / 1024 / 1024, 2),
                "remaining_mb": round((quota.storage_limit - quota.storage_used) / 1024 / 1024, 2),
            },
            "monthly_token": {
                "used": quota.monthly_token_used,
                "limit": quota.monthly_token_limit,
                "remaining": quota.monthly_token_limit - quota.monthly_token_used,
            },
            "total_chapters_generated": quota.total_chapters_generated,
        }
