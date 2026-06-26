"""生成计费 Phase 3 回归：算成本/扣减/退款幂等/无模型 no-op/余额不足 402。"""
import pytest
from fastapi import HTTPException

import app.models  # noqa: F401  触发全部 mapper 注册
from app.models.model_catalog import ModelCatalog
from app.services.quota_service import QuotaService
from app.services.generation_billing_service import (
    charge_generation,
    compute_generation_cost,
    refund_generation,
)


async def _seed_model(db, code="m", price=10):
    db.add(ModelCatalog(code=code, display_name=code, min_tier="free", credit_price=price, is_active=True))
    await db.commit()


@pytest.mark.asyncio
async def test_compute_cost(db_session):
    await _seed_model(db_session, "m", 10)
    assert await compute_generation_cost(db_session, None, False) == 0       # 未指定模型 → 0
    assert await compute_generation_cost(db_session, "m", False) == 10
    assert await compute_generation_cost(db_session, "m", True) == 15        # +润色 5
    assert await compute_generation_cost(db_session, "m", False, chapters=3) == 30
    assert await compute_generation_cost(db_session, "nope", False) == 0     # 未知模型 → 0


@pytest.mark.asyncio
async def test_charge_and_refund_idempotent(db_session):
    await _seed_model(db_session, "m", 10)
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(1)  # 60 积分
    charged = await charge_generation(db_session, 1, "m", True, ref_key="t1", chapters=2)  # (10+5)*2=30
    assert charged == 30
    assert (await svc.get_or_create_quota(1)).credit_balance == 30
    # 退款
    assert await refund_generation(db_session, 1, ref_key="t1") == 30
    assert (await svc.get_or_create_quota(1)).credit_balance == 60
    # 退款幂等
    assert await refund_generation(db_session, 1, ref_key="t1") == 0
    assert (await svc.get_or_create_quota(1)).credit_balance == 60


@pytest.mark.asyncio
async def test_charge_noop_without_model(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(2)
    assert await charge_generation(db_session, 2, None, False, ref_key="t2") == 0  # 无模型 → 不扣
    assert (await svc.get_or_create_quota(2)).credit_balance == 60
    # 无扣费记录 → 退款 no-op
    assert await refund_generation(db_session, 2, ref_key="t2") == 0


@pytest.mark.asyncio
async def test_charge_insufficient_402(db_session):
    await _seed_model(db_session, "big", 100)
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(3)  # 60 < 100
    with pytest.raises(HTTPException) as ei:
        await charge_generation(db_session, 3, "big", False, ref_key="t3")
    assert ei.value.status_code == 402
    assert (await svc.get_or_create_quota(3)).credit_balance == 60  # 未扣
