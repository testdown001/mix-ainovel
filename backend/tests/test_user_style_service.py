import asyncio
from types import SimpleNamespace

from app.services.user_style_service import UserStyleService


class _DummyScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _DummyExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return _DummyScalarResult(self._value)


class _DummySession:
    def __init__(self, value):
        self._value = value

    async def execute(self, stmt):
        return _DummyExecuteResult(self._value)


def test_user_style_service_prefetch_user_style(monkeypatch):
    from app.services import user_style_service as module

    preference = SimpleNamespace(style_preset="cinematic")

    class _SessionContext:
        async def __aenter__(self):
            return _DummySession(preference)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(module, "AsyncSessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(module, "build_user_style_prompt", lambda pref: "用户规则")

    service = UserStyleService()
    rules, preset = asyncio.run(service.prefetch_user_style(7))

    assert rules == "用户规则"
    assert preset == "cinematic"
