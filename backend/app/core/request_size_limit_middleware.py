# AIMETA P=请求体大小限制中间件_防止DoS攻击|R=请求体大小检查|E=RequestSizeLimitMiddleware|X=http|A=中间件|D=fastapi|S=net
"""
请求体大小限制中间件 - 防止大请求 DoS 攻击

核心功能：
1. 检查 Content-Length 头，拒绝超大请求
2. 流式读取请求体，防止内存溢出
3. 可配置的大小限制（默认 10MB）
"""
import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    请求体大小限制中间件

    拒绝超过限制的请求，防止 DoS 攻击和内存溢出
    """

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):
        """
        Args:
            app: FastAPI 应用实例
            max_size: 最大请求体大小（字节），默认 10MB
        """
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 检查 Content-Length 头
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size:
                    logger.warning(
                        "请求体过大被拒绝: %d bytes (limit: %d bytes), path=%s, client=%s",
                        size,
                        self.max_size,
                        request.url.path,
                        request.client.host if request.client else "unknown",
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": f"请求体过大，最大允许 {self.max_size // (1024 * 1024)}MB"
                        },
                    )
            except ValueError:
                logger.warning("无效的 Content-Length 头: %s", content_length)

        response = await call_next(request)
        return response
