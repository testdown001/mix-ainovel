# AIMETA P=安全响应头中间件_添加安全HTTP头|R=安全头注入|E=SecurityHeadersMiddleware|X=http|A=中间件|D=fastapi|S=net
"""
安全响应头中间件 - 添加标准安全 HTTP 头

核心功能：
1. X-Content-Type-Options: nosniff - 防止 MIME 类型嗅探
2. X-Frame-Options: DENY - 防止点击劫持
3. X-XSS-Protection: 1; mode=block - XSS 过滤器
4. Strict-Transport-Security: HTTPS 强制（生产环境）
5. Content-Security-Policy: 内容安全策略
6. Referrer-Policy: 控制 Referer 头泄露
"""
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全响应头中间件

    为所有响应添加标准安全头，提升应用安全性
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # 基础安全头（所有环境）
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content-Security-Policy（宽松策略，适配前后端分离）
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Vue 需要 unsafe-eval
            "style-src 'self' 'unsafe-inline'",  # 内联样式
            "img-src 'self' data: https:",  # 允许外部图片
            "font-src 'self' data:",
            "connect-src 'self' https:",  # API 调用
            "frame-ancestors 'none'",  # 等同于 X-Frame-Options: DENY
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # HSTS（仅生产环境 + HTTPS）
        if not settings.debug and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response
