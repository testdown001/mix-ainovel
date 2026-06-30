# AIMETA P=限流中间件_API请求限流|R=请求限流_用户隔离|E=rate_limit_middleware|X=http|A=中间件|D=fastapi|S=net
"""
API 限流中间件 - IP 级兜底 + 用户级限流

核心功能：
1. 中间件层自行解析 JWT 提取用户标识符，不依赖路由层 Depends
2. 已认证用户使用 username 级限流
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

# 前端静态资源前缀/后缀：当 FastAPI 直接服务前端 dist 时（main.py 的 SPA 挂载），
# 浏览器加载 SPA 会并发拉取大量 /assets/*.js|css 分片，且这些请求不携带 JWT，
# 会全部落到 IP 级限流（ip_rps）从而被误判为 429。静态资源无需限流，直接放行。
# 这与 Go 网关只对 /api 分组挂限流（gateway/cmd/gateway/main.go）的策略保持一致。
_STATIC_PREFIXES = ("/assets/",)
_STATIC_SUFFIXES = (
    ".js", ".mjs", ".css", ".map",
    ".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif",
    ".woff", ".woff2", ".ttf", ".eot",
    ".txt", ".webmanifest",
)

# 敏感端点（登录/注册）使用更严格的 IP 限流
_AUTH_PATHS = frozenset(["/api/auth/token", "/api/auth/users", "/api/auth/send-code", "/api/auth/reset-password", "/api/auth/phone/send-code", "/api/auth/phone/login"])
_GENERAL_RPM_CONFIG_KEY = "rate_limit.requests_per_minute"
_USER_RPS_CONFIG_KEY = "rate_limit.user_rps"
_IP_RPS_CONFIG_KEY = "rate_limit.ip_rps"
_AUTH_RPM_CONFIG_KEY = "rate_limit.auth_rpm"
_RATE_LIMIT_CONFIG_KEYS = (
    _GENERAL_RPM_CONFIG_KEY,
    _USER_RPS_CONFIG_KEY,
    _IP_RPS_CONFIG_KEY,
    _AUTH_RPM_CONFIG_KEY,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    API 请求限流中间件

    限流策略（阈值均来自 SystemConfig rate_limit.*，缺失时回退 settings 默认）：
    - 管理员: 一律放行（读 JWT is_admin，与 Go 网关 isAdmin→Next 对齐）
    - 已认证用户（sub 维度）: general_rpm req/min（默认 200）, user_rps req/sec（默认 10）
    - 未认证 IP（IP 维度）: general_rpm req/min（默认 200）, ip_rps req/sec（默认 20）
    - 敏感端点（IP 维度）: auth_rpm req/min（默认 30，暴力破解防护）
    """

    def __init__(self, app):
        super().__init__(app)
        # TTLCache：maxsize 限制最大条目数，ttl 控制过期时间（秒）
        # 条目格式: (minute_count, minute_start, second_count, second_start)
        self.user_requests: TTLCache = TTLCache(maxsize=10000, ttl=120)
        self.ip_requests: TTLCache = TTLCache(maxsize=50000, ttl=120)
        self.auth_requests: TTLCache = TTLCache(maxsize=10000, ttl=120)

        # 限流配置默认值（均可被 SystemConfig rate_limit.* 覆盖，下一次请求即生效）
        self.general_rpm_default = settings.api_rate_limit_requests_per_minute
        self.user_rps_default = settings.api_rate_limit_user_rps
        self.ip_rps_default = settings.api_rate_limit_ip_rps
        self.auth_rpm_default = settings.api_rate_limit_auth_rpm

    @staticmethod
    def _is_static_asset(path: str) -> bool:
        """前端静态资源请求（/assets/* 或带静态文件后缀）一律放行，不参与限流。"""
        return path.startswith(_STATIC_PREFIXES) or path.endswith(_STATIC_SUFFIXES)

    @staticmethod
    def _parse_positive_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    async def _load_rate_limits(self) -> Tuple[int, int, int, int]:
        """一次性读取四项限流阈值（单个 DB 查询）。缺失/非法的项回退到对应默认值。

        返回 (general_rpm, user_rps, ip_rps, auth_rpm)。
        """
        values: Dict[str, str] = {}
        try:
            async with AsyncSessionLocal() as session:
                values = await SystemConfigRepository(session).get_many(_RATE_LIMIT_CONFIG_KEYS)
        except Exception:
            logger.exception("读取限流系统配置失败，全部回退到默认阈值")

        general_rpm = self._parse_positive_int(values.get(_GENERAL_RPM_CONFIG_KEY)) or self.general_rpm_default
        user_rps = self._parse_positive_int(values.get(_USER_RPS_CONFIG_KEY)) or self.user_rps_default
        ip_rps = self._parse_positive_int(values.get(_IP_RPS_CONFIG_KEY)) or self.ip_rps_default
        auth_rpm = self._parse_positive_int(values.get(_AUTH_RPM_CONFIG_KEY)) or self.auth_rpm_default
        return general_rpm, user_rps, ip_rps, auth_rpm

    def _extract_user_claims(self, request: Request) -> Tuple[Optional[str], bool]:
        """从 Authorization header 解析 JWT，返回 (用户标识, 是否管理员)。失败返回 (None, False)。

        关闭 aud 校验：与 security.decode_access_token 一致——aud 仅供 Go 网关校验，
        FastAPI 侧不依赖它。不关闭则带 aud 的新 token 会触发 JWTClaimsError，
        导致已认证用户被误判为未认证而落入 IP 桶。
        """
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None, False
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_aud": False},
            )
        except JWTError:
            return None, False
        sub = payload.get("sub")
        identifier = str(sub) if sub else None
        is_admin = bool(payload.get("is_admin", False))
        return identifier, is_admin

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP（支持 X-Forwarded-For）。"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()  # 取末段：客户端伪造的 XFF 只在左侧，末段是最接近本服务的可信跳
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
        if path in _SKIP_PATHS or self._is_static_asset(path):
            return await call_next(request)

        # 先解析身份：管理员一律放行，与 Go 网关 isAdmin→Next 保持一致
        user_identifier, is_admin = self._extract_user_claims(request)
        if is_admin:
            return await call_next(request)

        general_rpm, user_rps, ip_rps, auth_rpm = await self._load_rate_limits()
        client_ip = self._get_client_ip(request)

        # 敏感端点：IP 级严格限流（暴力破解防护，发生在拿到 JWT 之前，管理员豁免对其无效）
        if path in _AUTH_PATHS:
            rejection = self._check_rate(
                self.auth_requests, f"auth:{client_ip}", auth_rpm, 0
            )
            if rejection:
                return rejection

        if user_identifier:
            # 已认证：用户级限流
            rejection = self._check_rate(
                self.user_requests, f"user:{user_identifier}", general_rpm, user_rps
            )
        else:
            # 未认证：IP 级限流
            rejection = self._check_rate(
                self.ip_requests, f"ip:{client_ip}", general_rpm, ip_rps
            )

        if rejection:
            return rejection

        response = await call_next(request)
        return response
