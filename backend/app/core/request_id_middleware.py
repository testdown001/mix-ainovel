# AIMETA P=请求ID中间件_为每个请求注入唯一标识|R=日志关联_请求追踪|E=RequestIdMiddleware|X=http
"""
Request ID 中间件 — 为每个请求生成唯一 ID，注入 logging context。

使用方式：
- 响应头自动附加 X-Request-ID
- 日志中通过 %(request_id)s 格式化输出
- 使用 contextvars 实现协程安全的 request_id 传递
"""
import contextvars
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# 协程级 request_id 上下文
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """日志过滤器：将 request_id 注入 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")  # type: ignore[attr-defined]
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求生成唯一 request_id 并设置到 contextvars。"""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
