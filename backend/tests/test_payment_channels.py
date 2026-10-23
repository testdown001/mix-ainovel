"""公开「已启用支付渠道」接口：只返回后台开了的渠道，顺序固定，不带密钥。"""
import pytest

import app.models  # noqa: F401  mapper 注册
from app.models.system_config import SystemConfig
from app.services.payment_service import PaymentService


async def _seed(session, **flags: str):
    for channel, value in flags.items():
        session.add(SystemConfig(key=f"pay.{channel}.enabled", value=value))
        # 带上一个密钥字段，确认接口不会把它漏出去
        session.add(SystemConfig(key=f"pay.{channel}.secret_key", value="sk_should_not_leak"))
    await session.commit()


@pytest.mark.asyncio
async def test_only_enabled_channels_in_fixed_order(db_session):
    await _seed(db_session, wechat="true", stripe="true", alipay="false")
    channels = await PaymentService(db_session).list_enabled_channels()
    assert [c["channel"] for c in channels] == ["stripe", "wechat"]
    assert channels[0]["label"] == "Stripe"
    for item in channels:
        assert set(item.keys()) == {"channel", "label"}


@pytest.mark.asyncio
async def test_no_channels_when_nothing_enabled(db_session):
    await _seed(db_session, alipay="0")
    assert await PaymentService(db_session).list_enabled_channels() == []


@pytest.mark.asyncio
async def test_enabled_flag_is_case_and_space_tolerant(db_session):
    await _seed(db_session, alipay=" True ")
    channels = await PaymentService(db_session).list_enabled_channels()
    assert [c["channel"] for c in channels] == ["alipay"]
