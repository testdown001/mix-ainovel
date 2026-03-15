# AIMETA P=限流中间件_API请求限流|R=请求限流_用户隔离|E=rate_limit_middleware|X=http|A=中间件|D=fastapi|S=net
"""
API 限流中间件 - 用户级请求限流

核心功能：
1. 每用户每分钟请求数限制
2. 每用户每秒请求数限制
3. 白名单支持（管理员、Premium 用户）
"""
import logging
import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    API 请求限流中间件

    限流策略：
    - 普通用户: 60 req/min, 10 req/sec
    - Premium 用户: 180 req/min, 30 req/sec
    - 管理员: 无限制
    """

    def __init__(self, app):
        super().__init__(app)
        # 用户请求计数: {user_id: (minute_count, minute_start, second_count, second_start)}
        self.user_requests: Dict[int, Tuple[int, float, int, float]] = defaultdict(
            lambda: (0, time.time(), 0, time.time())
        )
        self.premium_users: set[int] = set()
        self.admin_users: set[int] = set()

        # 限流配置
        self.default_rpm = 60  # 普通用户每分钟请求数
        self.default_rps = 10  # 普通用户每秒请求数
        self.premium_rpm = 180  # Premium 用户每分钟请求数
        self.premium_rps = 30  # Premium 用户每秒请求数

    def set_premium_user(self, user_id: int):
        """设置 Premium 用户"""
        self.premium_users.add(user_id)

    def set_admin_user(self, user_id: int):
        """设置管理员用户"""
        self.admin_users.add(user_id)

    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查和静态资源
        if request.url.path in ["/health", "/api/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # 获取用户 ID（从 JWT token 或其他认证方式）
        user_id = getattr(request.state, "user_id", None)

        if user_id is None:
            # 未认证用户，不限流（由认证中间件处理）
            return await call_next(request)

        # 管理员不限流
        if user_id in self.admin_users:
            return await call_next(request)

        # 检查限流
        is_premium = user_id in self.premium_users
        rpm_limit = self.premium_rpm if is_premium else self.default_rpm
        rps_limit = self.premium_rps if is_premium else self.default_rps

        now = time.time()
        minute_count, minute_start, second_count, second_start = self.user_requests[user_id]

        # 重置分钟计数器
        if now - minute_start >= 60:
            minute_count = 0
            minute_start = now

        # 重置秒计数器
        if now - second_start >= 1:
            second_count = 0
            second_start = now

        # 检查每分钟限制
        if minute_count >= rpm_limit:
            logger.warning(f"用户 {user_id} 超过每分钟请求限制: {minute_count}/{rpm_limit}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"请求过于频繁，请稍后再试。限制: {rpm_limit} 请求/分钟",
                    "retry_after": int(60 - (now - minute_start)),
                },
            )

        # 检查每秒限制
        if second_count >= rps_limit:
            logger.warning(f"用户 {user_id} 超过每秒请求限制: {second_count}/{rps_limit}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"请求过于频繁，请稍后再试。限制: {rps_limit} 请求/秒",
                    "retry_after": 1,
                },
            )

        # 更新计数器
        minute_count += 1
        second_count += 1
        self.user_requests[user_id] = (minute_count, minute_start, second_count, second_start)

        # 添加限流信息到响应头
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rpm_limit)
        response.headers["X-RateLimit-Remaining"] = str(rpm_limit - minute_count)
        response.headers["X-RateLimit-Reset"] = str(int(minute_start + 60))

        return response
