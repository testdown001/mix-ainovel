import asyncio

from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.core.config import settings
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.db.system_config_defaults import SYSTEM_CONFIG_DEFAULTS


async def _call_next(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


async def _noop_app(scope, receive, send):
    return None


def _build_request(path: str = "/api/novels/demo") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "root_path": "",
        }
    )


def test_system_config_defaults_include_rate_limit_requests_per_minute():
    entry = next(item for item in SYSTEM_CONFIG_DEFAULTS if item.key == "rate_limit.requests_per_minute")

    assert entry.value_getter(settings) == str(settings.api_rate_limit_requests_per_minute)
    assert settings.api_rate_limit_requests_per_minute == 200


def test_static_assets_bypass_rate_limit(monkeypatch):
    """前端静态资源（/assets/*.js 等）必须放行，避免 SPA 并发加载分片时被误判 429。"""
    middleware = RateLimitMiddleware(_noop_app)

    async def _tiny_limit() -> int:
        return 1  # 极严格：每分钟仅 1 次，若静态资源参与限流则第 2 次即 429

    monkeypatch.setattr(middleware, "_load_general_rpm_limit", _tiny_limit)

    for path in (
        "/assets/index-C0aFyBBz.js",
        "/assets/index-BbC0nFC0.css",
        "/favicon.ico",
        "/assets/AdminView-3zd2BuVH.css",
    ):
        for _ in range(3):  # 连续多次仍不应被限流
            resp = asyncio.run(middleware.dispatch(_build_request(path), _call_next))
            assert resp.status_code == 200, f"静态资源被误限流: {path}"


def test_rate_limit_middleware_reloads_requests_per_minute_each_request(monkeypatch):
    middleware = RateLimitMiddleware(_noop_app)
    limits = iter([1, 2, 2])

    async def _next_limit() -> int:
        return next(limits)

    monkeypatch.setattr(middleware, "_load_general_rpm_limit", _next_limit)

    first = asyncio.run(middleware.dispatch(_build_request(), _call_next))
    second = asyncio.run(middleware.dispatch(_build_request(), _call_next))
    third = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
