import asyncio

from app.core import security as module


def test_resolve_user_id_from_payload_prefers_explicit_user_id(monkeypatch):
    monkeypatch.setattr(module, "_USERNAME_USER_ID_CACHE", {})

    user_id = asyncio.run(module.resolve_user_id_from_payload({"sub": "admin", "user_id": 7}))

    assert user_id == 7


def test_resolve_user_id_from_payload_falls_back_to_username_lookup(monkeypatch):
    monkeypatch.setattr(module, "_USERNAME_USER_ID_CACHE", {})

    async def _fake_lookup(username: str):
        assert username == "admin"
        return 9

    monkeypatch.setattr(module, "_lookup_user_id_by_username", _fake_lookup)

    user_id = asyncio.run(module.resolve_user_id_from_payload({"sub": "admin"}))

    assert user_id == 9
