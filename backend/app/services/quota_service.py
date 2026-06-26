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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from ..models.user_quota import UserQuota
from ..models.credit_log import CreditLog

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

    # 积分制月度发放额度（档位默认值；Plan.monthly_credits>0 时以套餐为准。
    # 后续可由 SystemConfig credits.monthly.* 覆写，Phase 3 接入）
    DEFAULT_FREE_MONTHLY_CREDITS = 60        # ≈10 篇章鱼1.0，体验额度
    DEFAULT_CREATOR_MONTHLY_CREDITS = 3000   # =300 篇章鱼2.0（10/天×30）
    DEFAULT_FLAGSHIP_MONTHLY_CREDITS = 18000  # =1800 篇章鱼2.0（60/天×30）
    CREDIT_RESET_DAYS = 30

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
                credit_balance=self.DEFAULT_FREE_MONTHLY_CREDITS,
                monthly_credit_grant=self.DEFAULT_FREE_MONTHLY_CREDITS,
                credit_reset_at=datetime.utcnow(),
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

    # ---------------- 积分制额度（月度池，30 天滚动重置） ----------------

    def _credit_grant_for_tier(self, tier: str) -> int:
        return {
            "creator": self.DEFAULT_CREATOR_MONTHLY_CREDITS,
            "flagship": self.DEFAULT_FLAGSHIP_MONTHLY_CREDITS,
        }.get(tier, self.DEFAULT_FREE_MONTHLY_CREDITS)

    async def check_and_reset_credit(self, quota: UserQuota) -> UserQuota:
        """积分滚动重置：首次初始化锚点；满 30 天则按是否累积重置/累加，与每月 token 重置同款。"""
        now = datetime.utcnow()
        if quota.credit_reset_at is None:
            quota.credit_reset_at = now
            await self.session.commit()
            return quota
        if now - quota.credit_reset_at >= timedelta(days=self.CREDIT_RESET_DAYS):
            if quota.credit_carryover:
                quota.credit_balance += quota.monthly_credit_grant
            else:
                quota.credit_balance = quota.monthly_credit_grant
            quota.credit_reset_at = now
            await self.session.commit()
            logger.info("重置积分: user_id=%s -> balance=%s", quota.user_id, quota.credit_balance)
        return quota

    async def _credit_log_exists(self, reason: str, ref_key: Optional[str]) -> bool:
        if not ref_key:
            return False
        stmt = select(CreditLog.id).where(
            CreditLog.reason == reason, CreditLog.ref_key == ref_key
        ).limit(1)
        return (await self.session.execute(stmt)).first() is not None

    async def has_credits(self, user_id: int, amount: int) -> bool:
        """是否有足够积分（不扣减）。"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_credit(quota)
        return quota.credit_balance >= amount

    async def consume_credits(
        self,
        user_id: int,
        amount: int,
        *,
        reason: str = "generate",
        ref_key: Optional[str] = None,
        note: Optional[str] = None,
    ) -> UserQuota:
        """扣减积分。余额不足抛 402；带 ref_key 时按 (reason, ref_key) 幂等(不重复扣)。"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_credit(quota)
        if amount <= 0:
            return quota
        if ref_key and await self._credit_log_exists(reason, ref_key):
            return quota  # 幂等：已扣过
        if quota.credit_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"积分不足：本次需 {amount} 积分，剩余 {quota.credit_balance}。"
                       f"可升级套餐或等待月度重置。",
            )
        quota.credit_balance -= amount
        self.session.add(CreditLog(
            user_id=user_id, delta=-amount, reason=reason, ref_key=ref_key,
            balance_after=quota.credit_balance, note=note,
        ))
        try:
            await self.session.commit()
        except IntegrityError:
            # 并发下同 ref 已入账 → 回滚，视为幂等已处理
            await self.session.rollback()
            return await self.get_or_create_quota(user_id)
        await self.session.refresh(quota)
        logger.info("扣减积分: user_id=%s amount=%s reason=%s ref=%s balance=%s",
                    user_id, amount, reason, ref_key, quota.credit_balance)
        return quota

    async def refund_credits(
        self,
        user_id: int,
        amount: int,
        *,
        ref_key: str,
        reason: str = "refund",
        note: Optional[str] = None,
    ) -> UserQuota:
        """退还积分（生成失败/取消）。按 (reason, ref_key) 幂等，避免重复退。"""
        quota = await self.get_or_create_quota(user_id)
        if amount <= 0 or not ref_key:
            return quota
        if await self._credit_log_exists(reason, ref_key):
            return quota  # 幂等：已退过
        quota.credit_balance += amount
        self.session.add(CreditLog(
            user_id=user_id, delta=amount, reason=reason, ref_key=ref_key,
            balance_after=quota.credit_balance, note=note,
        ))
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            return await self.get_or_create_quota(user_id)
        await self.session.refresh(quota)
        logger.info("退还积分: user_id=%s amount=%s ref=%s balance=%s",
                    user_id, amount, ref_key, quota.credit_balance)
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

        tier = self._derive_tier(plan)
        plan_credits = getattr(plan, "monthly_credits", 0) or 0
        grant = plan_credits if plan_credits > 0 else self._credit_grant_for_tier(tier)

        quota.is_premium = True
        quota.premium_expires_at = expires_at
        quota.plan_tier = tier
        quota.daily_chapter_limit = plan_daily if plan_daily > 0 else self.PREMIUM_DAILY_CHAPTER_LIMIT
        quota.storage_limit = self.PREMIUM_STORAGE_LIMIT
        quota.monthly_token_limit = self.PREMIUM_MONTHLY_TOKEN_LIMIT
        # 积分：激活即发放当期额度，并重置滚动锚点
        quota.monthly_credit_grant = grant
        quota.credit_balance = grant
        quota.credit_reset_at = datetime.utcnow()

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
        # 积分：发放额度回落 free；当前余额不强制清零，到期滚动重置时自然回落
        quota.monthly_credit_grant = self.DEFAULT_FREE_MONTHLY_CREDITS

        await self.session.commit()
        await self.session.refresh(quota)

        logger.info(f"降级为普通用户: user_id={user_id}")
        return quota

    async def get_quota_info(self, user_id: int) -> dict:
        """获取用户配额信息"""
        quota = await self.get_or_create_quota(user_id)
        quota = await self.check_and_reset_daily_quota(quota)
        quota = await self.check_and_reset_monthly_quota(quota)
        quota = await self.check_and_reset_credit(quota)

        return {
            "user_id": user_id,
            "is_premium": quota.is_premium_active,
            "plan_tier": quota.effective_tier,
            "credit": {
                "balance": quota.credit_balance,
                "monthly_grant": quota.monthly_credit_grant,
                "carryover": bool(quota.credit_carryover),
                "reset_at": quota.credit_reset_at.isoformat() if quota.credit_reset_at else None,
            },
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
