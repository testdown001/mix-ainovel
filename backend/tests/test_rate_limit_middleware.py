import asyncio

from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.core.config import settings
from app.core.security import create_access_token
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.db.system_config_defaults import SYSTEM_CONFIG_DEFAULTS


async def _call_next(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


async def _noop_app(scope, receive, send):
    return None


def _build_request(path: str = "/api/novels/demo", *, token: str | None = None) -> Request:
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "root_path": "",
        }
    )


def _patch_limits(monkeypatch, middleware, general_rpm=200, user_rps=100, ip_rps=100, auth_rpm=100):
    async def _loader():
        return (general_rpm, user_rps, ip_rps, auth_rpm)

    monkeypatch.setattr(middleware, "_load_rate_limits", _loader)


# ---------- 系统配置默认项 ----------

def test_system_config_defaults_include_rate_limit_keys():
    keys = {item.key for item in SYSTEM_CONFIG_DEFAULTS}
    assert {
        "rate_limit.requests_per_minute",
        "rate_limit.user_rps",
        "rate_limit.ip_rps",
        "rate_limit.auth_rpm",
    }.issubset(keys)

    rpm = next(i for i in SYSTEM_CONFIG_DEFAULTS if i.key == "rate_limit.requests_per_minute")
    assert rpm.value_getter(settings) == str(settings.api_rate_limit_requests_per_minute)
    assert settings.api_rate_limit_requests_per_minute == 200
    # 新默认：放宽未认证 SPA 突发与登录端点
    assert settings.api_rate_limit_ip_rps == 20
    assert settings.api_rate_limit_auth_rpm == 30


# ---------- 静态资源放行 ----------

def test_static_assets_bypass_rate_limit(monkeypatch):
    """前端静态资源（/assets/*.js 等）必须放行，避免 SPA 并发加载分片时被误判 429。"""
    middleware = RateLimitMiddleware(_noop_app)
    _patch_limits(monkeypatch, middleware, general_rpm=1, ip_rps=1)  # 极严格

    for path in (
        "/assets/index-C0aFyBBz.js",
        "/assets/index-BbC0nFC0.css",
        "/favicon.ico",
        "/assets/AdminView-3zd2BuVH.css",
    ):
        for _ in range(3):
            resp = asyncio.run(middleware.dispatch(_build_request(path), _call_next))
            assert resp.status_code == 200, f"静态资源被误限流: {path}"


# ---------- 每请求重载阈值 ----------

def test_rate_limit_middleware_reloads_each_request(monkeypatch):
    middleware = RateLimitMiddleware(_noop_app)
    limits = iter([(1, 100, 100, 100), (2, 100, 100, 100), (2, 100, 100, 100)])

    async def _loader():
        return next(limits)

    monkeypatch.setattr(middleware, "_load_rate_limits", _loader)

    first = asyncio.run(middleware.dispatch(_build_request(), _call_next))
    second = asyncio.run(middleware.dispatch(_build_request(), _call_next))
    third = asyncio.run(middleware.dispatch(_build_request(), _call_next))

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


# ---------- 管理员豁免 ----------

def test_admin_is_exempt_from_rate_limit(monkeypatch):
    """管理员一律放行，与 Go 网关 isAdmin→Next 对齐：极严格阈值下仍连续 200。"""
    middleware = RateLimitMiddleware(_noop_app)
    _patch_limits(monkeypatch, middleware, general_rpm=1, user_rps=1, ip_rps=1, auth_rpm=1)
    admin_token = create_access_token(1, extra_claims={"is_admin": True})

    for _ in range(5):
        resp = asyncio.run(middleware.dispatch(_build_request(token=admin_token), _call_next))
        assert resp.status_code == 200


def test_non_admin_user_still_limited(monkeypatch):
    """普通已认证用户不豁免：超过 user_rps 即 429（证明豁免只对管理员生效）。"""
    middleware = RateLimitMiddleware(_noop_app)
    _patch_limits(monkeypatch, middleware, general_rpm=100, user_rps=1)
    user_token = create_access_token(2, extra_claims={"is_admin": False})

    first = asyncio.run(middleware.dispatch(_build_request(token=user_token), _call_next))
    second = asyncio.run(middleware.dispatch(_build_request(token=user_token), _call_next))
    assert first.status_code == 200
    assert second.status_code == 429


# ---------- 带 aud 的 token 解码（潜在 bug 修复回归） ----------

def test_extract_claims_decodes_token_with_aud():
    """token 带 aud 时仍须成功解析出 (sub, is_admin)；漏 verify_aud=False 会令已认证用户被误判为未认证。"""
    middleware = RateLimitMiddleware(_noop_app)

    admin_token = create_access_token(7, extra_claims={"is_admin": True})
    identifier, is_admin = middleware._extract_user_claims(_build_request(token=admin_token))
    assert identifier == "7"
    assert is_admin is True

    user_token = create_access_token(8, extra_claims={"is_admin": False})
    identifier, is_admin = middleware._extract_user_claims(_build_request(token=user_token))
    assert identifier == "8"
    assert is_admin is False


def test_extract_claims_no_header_returns_none():
    middleware = RateLimitMiddleware(_noop_app)
    identifier, is_admin = middleware._extract_user_claims(_build_request())
    assert identifier is None
    assert is_admin is False
