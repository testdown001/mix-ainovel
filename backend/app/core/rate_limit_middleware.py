# AIMETA P=限流中间件_API请求限流|R=请求限流_用户隔离|E=rate_limit_middleware|X=http|A=中间件|D=fastapi|S=net
"""
API 限流中间件 - IP 级兜底 + 用户级限流

核心功能：
1. 中间件层自行解析 JWT 提取 user_id，不依赖路由层 Depends
2. 已认证用户使用 user_id 级限流
3. 未认证用户使用 IP 级限流（登录、注册等端点的暴力破解防护）
4. 使用 TTLCache 自动清理过期条目，防止内存泄漏
"""
import logging
import time
from typing import Any, Dict, Optional, Tuple

from cachetools import TTLCache
from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from ..db.session import AsyncSessionLocal
from ..repositories.system_config_repository import SystemConfigRepository

logger = logging.getLogger(__name__)

# 免限流路径
_SKIP_PATHS = frozenset(["/health", "/api/health", "/docs", "/openapi.json"])

# 敏感端点（登录/注册）使用更严格的 IP 限流
_AUTH_PATHS = frozenset(["/api/auth/token", "/api/auth/users", "/api/auth/send-code"])
_GENERAL_RPM_CONFIG_KEY = "rate_limit.requests_per_minute"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    API 请求限流中间件

    限流策略：
    - 已认证用户（user_id 维度）: 60 req/min, 10 req/sec
    - 未认证 IP（IP 维度）: 30 req/min, 5 req/sec
    - 敏感端点（IP 维度）: 5 req/min（暴力破解防护）
    """

    def __init__(self, app):
        super().__init__(app)
        # TTLCache：maxsize 限制最大条目数，ttl 控制过期时间（秒）
        # 条目格式: (minute_count, minute_start, second_count, second_start)
        self.user_requests: TTLCache = TTLCache(maxsize=10000, ttl=120)
        self.ip_requests: TTLCache = TTLCache(maxsize=50000, ttl=120)
        self.auth_requests: TTLCache = TTLCache(maxsize=10000, ttl=120)

        # 限流配置
        self.general_rpm_default = settings.api_rate_limit_requests_per_minute
        self.user_rps = 10
        self.ip_rps = 5
        self.auth_rpm = 5  # 敏感端点每分钟最多 5 次

    @staticmethod
    def _parse_positive_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    async def _load_general_rpm_limit(self) -> int:
        try:
            async with AsyncSessionLocal() as session:
                config = await SystemConfigRepository(session).get_by_key(_GENERAL_RPM_CONFIG_KEY)
            parsed = self._parse_positive_int(config.value if config else None)
            return parsed or self.general_rpm_default
        except Exception:
            logger.exception(
                "读取系统配置 %s 失败，回退到默认限流值 %s req/min",
                _GENERAL_RPM_CONFIG_KEY,
                self.general_rpm_default,
            )
            return self.general_rpm_default

    def _extract_user_id(self, request: Request) -> Optional[int]:
        """从 Authorization header 解析 JWT，提取 user_id。失败返回 None。"""
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
            return int(payload.get("sub", 0)) or None
        except (JWTError, ValueError):
            return None

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP（支持 X-Forwarded-For）。"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _check_rate(
        self, cache: TTLCache, key: str, rpm_limit: int, rps_limit: int
    ) -> Optional[JSONResponse]:
        """通用限流检查。返回 429 响应或 None（放行）。"""
        now = time.time()
        entry = cache.get(key, (0, now, 0, now))
        minute_count, minute_start, second_count, second_start = entry

        # 重置分钟计数器
        if now - minute_start >= 60:
            minute_count = 0
            minute_start = now

        # 重置秒计数器
        if now - second_start >= 1:
            second_count = 0
            second_start = now

        if minute_count >= rpm_limit:
            logger.warning("限流触发 [%s]: %d/%d req/min", key, minute_count, rpm_limit)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"请求过于频繁，请稍后再试。限制: {rpm_limit} 请求/分钟",
                    "retry_after": int(60 - (now - minute_start)),
                },
            )

        if rps_limit and second_count >= rps_limit:
            logger.warning("限流触发 [%s]: %d/%d req/sec", key, second_count, rps_limit)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"请求过于频繁，请稍后再试。限制: {rps_limit} 请求/秒",
                    "retry_after": 1,
                },
            )

        # 更新计数
        cache[key] = (minute_count + 1, minute_start, second_count + 1, second_start)
        return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        general_rpm = await self._load_general_rpm_limit()
        client_ip = self._get_client_ip(request)

        # 敏感端点：IP 级严格限流
        if path in _AUTH_PATHS:
            rejection = self._check_rate(
                self.auth_requests, f"auth:{client_ip}", self.auth_rpm, 0
            )
            if rejection:
                return rejection

        # 尝试提取 user_id
        user_id = self._extract_user_id(request)

        if user_id:
            # 已认证：用户级限流
            rejection = self._check_rate(
                self.user_requests, f"user:{user_id}", general_rpm, self.user_rps
            )
        else:
            # 未认证：IP 级限流
            rejection = self._check_rate(
                self.ip_requests, f"ip:{client_ip}", general_rpm, self.ip_rps
            )

        if rejection:
            return rejection

        response = await call_next(request)
        return response
