"""邮件双通道（SMTP / Resend）：通道解析、Resend 配置加载与发送。"""
import asyncio

import pytest

import app.models  # noqa: F401  mapper 注册
from fastapi import HTTPException as FastAPIHTTPException
from app.services import auth_service as auth_service_module
from app.services.auth_service import AuthService


def _make_auth(configs):
    """构造一个仅带 system_config_repo 桩的 AuthService（不连 DB）。"""
    svc = AuthService.__new__(AuthService)

    class _Repo:
        async def get_by_key(self, key):
            v = configs.get(key)
            return type("C", (), {"value": v})() if v is not None else None

    svc.system_config_repo = _Repo()
    return svc


# ---------- 通道解析 ----------

def test_provider_defaults_to_smtp_when_unset():
    svc = _make_auth({})
    assert asyncio.run(svc._resolve_email_provider()) == "smtp"


def test_provider_resend_when_set():
    svc = _make_auth({"email.provider": "Resend"})  # 大小写/空格容错
    assert asyncio.run(svc._resolve_email_provider()) == "resend"


def test_provider_falls_back_to_smtp_on_garbage():
    svc = _make_auth({"email.provider": "mailgun"})
    assert asyncio.run(svc._resolve_email_provider()) == "smtp"


# ---------- Resend 配置加载 ----------

def test_load_resend_config_incomplete_returns_none():
    svc = _make_auth({"resend.api_key": "re_x"})  # 缺 from
    assert asyncio.run(svc._load_resend_config()) is None


def test_load_resend_config_complete():
    svc = _make_auth({"resend.api_key": "re_x", "resend.from": "验证码 <noreply@a.com>"})
    cfg = asyncio.run(svc._load_resend_config())
    assert cfg == {"resend.api_key": "re_x", "resend.from": "验证码 <noreply@a.com>"}


# ---------- Resend 发送 ----------

class _FakeResp:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json


def _patch_httpx(monkeypatch, resp, captured):
    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return resp

    monkeypatch.setattr(auth_service_module.httpx, "AsyncClient", _FakeClient)


def test_send_via_resend_success(monkeypatch):
    captured = {}
    _patch_httpx(monkeypatch, _FakeResp(200, {"id": "email_123"}), captured)
    svc = _make_auth({})
    asyncio.run(
        svc._send_via_resend(
            "u@x.com",
            "注册验证码",
            "<p>code</p>",
            {"resend.api_key": "re_k", "resend.from": "验证码 <noreply@a.com>"},
        )
    )
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_k"
    assert captured["json"]["from"] == "验证码 <noreply@a.com>"
    assert captured["json"]["to"] == ["u@x.com"]
    assert captured["json"]["subject"] == "注册验证码"
    assert captured["json"]["html"] == "<p>code</p>"


def test_send_via_resend_api_error_raises_500(monkeypatch):
    captured = {}
    _patch_httpx(monkeypatch, _FakeResp(422, text='{"message":"domain not verified"}'), captured)
    svc = _make_auth({})
    with pytest.raises(FastAPIHTTPException) as ei:
        asyncio.run(
            svc._send_via_resend(
                "u@x.com",
                "注册验证码",
                "<p>code</p>",
                {"resend.api_key": "re_k", "resend.from": "noreply@a.com"},
            )
        )
    assert ei.value.status_code == 500
