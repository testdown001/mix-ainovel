"""新增登录方式：短信服务 + 手机号验证码登录即注册 + OAuth 启用开关。"""
import asyncio

import pytest

import app.models  # noqa: F401  mapper 注册
from app.db.base import Base
from app.models.system_config import SystemConfig
from app.services.auth_service import AuthService
from app.services.sms_service import SmsService

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


# ---------- SmsService ----------

def test_sms_percent_encode_rfc3986():
    assert SmsService._percent_encode("a b") == "a%20b"
    assert SmsService._percent_encode("~") == "~"
    assert SmsService._percent_encode("+") == "%2B"


def _make_sms(configs):
    svc = SmsService.__new__(SmsService)
    class _Repo:
        async def get_by_key(self, key):
            v = configs.get(key)
            return type("C", (), {"value": v})() if v is not None else None
    svc.config_repo = _Repo()
    return svc


def test_sms_mock_provider_returns_true_without_network():
    svc = _make_sms({"sms.provider": "mock"})
    assert asyncio.run(svc.send_code("13800138000", "123456")) is True


def test_sms_aliyun_unconfigured_returns_false():
    svc = _make_sms({"sms.provider": "aliyun"})  # 缺密钥
    assert asyncio.run(svc.send_code("13800138000", "123456")) is False


# ---------- 手机号验证码登录即注册 ----------

def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _seed_config(session, **kv):
    for k, v in kv.items():
        session.add(SystemConfig(key=k, value=v))
    await session.commit()


async def _run_phone_flow():
    engine, Session = _make_sessionmaker()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as session:
        await _seed_config(session, **{"auth.phone_enabled": "true", "sms.provider": "mock"})
        svc = AuthService(session)
        # 强制走内存验证码路径（测试无 Redis）
        svc._get_redis = lambda: _async_none()  # type: ignore

        phone = "13912345678"
        await svc.send_phone_code(phone)
        code, _ = svc._verification_cache[f"phone_login:{phone}"]

        # 首次登录即注册
        token = await svc.login_with_phone(phone, code)
        assert token.access_token
        user = await svc.user_repo.get_by_phone(phone)
        assert user is not None and user.phone == phone

        # 验证码一次性：成功后再用任意码都应被拒
        try:
            await svc.login_with_phone(phone, "000000")
            raise AssertionError("错误/失效验证码应被拒")
        except Exception as e:
            assert "验证码" in str(e)
    await engine.dispose()


async def _async_none():
    return None


def test_phone_code_login_creates_account():
    asyncio.run(_run_phone_flow())


def test_phone_login_disabled_raises():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            svc = AuthService(session)
            svc._get_redis = lambda: _async_none()  # type: ignore
            try:
                await svc.send_phone_code("13912345678")
                raise AssertionError("未启用应抛错")
            except Exception as e:
                assert "未启用" in str(e)
        await engine.dispose()
    asyncio.run(_run())
