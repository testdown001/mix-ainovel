# AIMETA P=限流服务_令牌桶限流|R=LLM调用限流_并发控制|E=TokenBucketLimiter|X=internal|A=限流器|D=asyncio|S=none
"""
LLM 调用限流服务 - Token Bucket + 并发槽控制

核心功能：
1. 每用户 TPM (Tokens Per Minute) 限流
2. 每用户并发槽控制
3. 公平调度，避免饥饿
4. 优雅降级支持
"""
import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserQuota:
    """用户配额信息"""
    tpm_limit: int = 100000  # 每分钟 token 限制
    max_concurrent: int = 3  # 最大并发数
    tokens: float = 100000.0  # 当前可用 tokens
    last_refill: float = field(default_factory=time.time)  # 上次补充时间
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(3))  # 并发信号量


class TokenBucketLimiter:
    """
    令牌桶限流器 + 并发槽控制

    特性：
    - Token-aware 限流：按实际消耗的 tokens 计费
    - 并发槽控制：限制每用户同时运行的请求数
    - 自动补充：每分钟补充 TPM 配额
    - 用户级隔离：不同用户独立配额
    """

    def __init__(
        self,
        default_tpm: int = 100000,
        default_concurrent: int = 3,
        premium_tpm: int = 300000,
        premium_concurrent: int = 8,
    ):
        """
        初始化限流器

        Args:
            default_tpm: 普通用户每分钟 token 限制
            default_concurrent: 普通用户最大并发数
            premium_tpm: Premium 用户每分钟 token 限制
            premium_concurrent: Premium 用户最大并发数
        """
        self.default_tpm = default_tpm
        self.default_concurrent = default_concurrent
        self.premium_tpm = premium_tpm
        self.premium_concurrent = premium_concurrent

        self.user_quotas: Dict[int, UserQuota] = {}
        self.premium_users: set[int] = set()  # Premium 用户集合
        self._lock = asyncio.Lock()

    def set_premium_user(self, user_id: int, is_premium: bool = True):
        """设置用户为 Premium"""
        if is_premium:
            self.premium_users.add(user_id)
        else:
            self.premium_users.discard(user_id)

    async def _get_or_create_quota(self, user_id: int) -> UserQuota:
        """获取或创建用户配额"""
        async with self._lock:
            if user_id not in self.user_quotas:
                is_premium = user_id in self.premium_users
                tpm = self.premium_tpm if is_premium else self.default_tpm
                concurrent = self.premium_concurrent if is_premium else self.default_concurrent

                self.user_quotas[user_id] = UserQuota(
                    tpm_limit=tpm,
                    max_concurrent=concurrent,
                    tokens=float(tpm),
                    last_refill=time.time(),
                    semaphore=asyncio.Semaphore(concurrent),
                )
                logger.info(f"创建用户配额: user_id={user_id}, tpm={tpm}, concurrent={concurrent}")

            return self.user_quotas[user_id]

    async def _refill_tokens(self, quota: UserQuota):
        """补充 tokens（按时间流逝比例）"""
        now = time.time()
        elapsed = now - quota.last_refill

        if elapsed > 0:
            # 每秒补充 TPM / 60 个 tokens
            refill_amount = (quota.tpm_limit / 60.0) * elapsed
            quota.tokens = min(quota.tpm_limit, quota.tokens + refill_amount)
            quota.last_refill = now

    async def acquire(
        self,
        user_id: int,
        estimated_tokens: int = 1000,
        timeout: float = 30.0,
    ) -> bool:
        """
        获取限流许可

        Args:
            user_id: 用户 ID
            estimated_tokens: 预估消耗的 tokens
            timeout: 超时时间（秒）

        Returns:
            是否成功获取许可

        Raises:
            asyncio.TimeoutError: 超时未获取到许可
        """
        quota = await self._get_or_create_quota(user_id)

        # 1. 获取并发槽
        try:
            await asyncio.wait_for(quota.semaphore.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"用户 {user_id} 并发槽获取超时")
            raise

        # 2. 检查并消耗 tokens
        try:
            start_time = time.time()
            while True:
                async with self._lock:
                    await self._refill_tokens(quota)

                    if quota.tokens >= estimated_tokens:
                        quota.tokens -= estimated_tokens
                        logger.debug(
                            f"用户 {user_id} 获取限流许可: "
                            f"消耗 {estimated_tokens} tokens, 剩余 {quota.tokens:.0f}"
                        )
                        return True

                # 检查超时
                if time.time() - start_time > timeout:
                    quota.semaphore.release()
                    logger.warning(f"用户 {user_id} token 配额获取超时")
                    raise asyncio.TimeoutError("Token 配额获取超时")

                # 等待一小段时间后重试
                await asyncio.sleep(0.5)

        except Exception:
            # 发生异常时释放并发槽
            quota.semaphore.release()
            raise

    def release(self, user_id: int):
        """释放并发槽"""
        if user_id in self.user_quotas:
            quota = self.user_quotas[user_id]
            quota.semaphore.release()
            logger.debug(f"用户 {user_id} 释放并发槽")

    async def get_quota_info(self, user_id: int) -> Dict:
        """获取用户配额信息"""
        quota = await self._get_or_create_quota(user_id)
        async with self._lock:
            await self._refill_tokens(quota)

        return {
            "user_id": user_id,
            "tpm_limit": quota.tpm_limit,
            "tokens_available": int(quota.tokens),
            "tokens_used": int(quota.tpm_limit - quota.tokens),
            "max_concurrent": quota.max_concurrent,
            "concurrent_available": quota.semaphore._value,
            "is_premium": user_id in self.premium_users,
        }


# 全局限流器实例
_global_limiter: Optional[TokenBucketLimiter] = None


def get_rate_limiter() -> TokenBucketLimiter:
    """获取全局限流器实例"""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = TokenBucketLimiter(
            default_tpm=100000,      # 普通用户 10 万 TPM
            default_concurrent=3,     # 普通用户 3 并发
            premium_tpm=300000,       # Premium 用户 30 万 TPM
            premium_concurrent=8,     # Premium 用户 8 并发
        )
    return _global_limiter
