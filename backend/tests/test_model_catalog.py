"""模型目录 Phase 2 回归：按档门控 / available 列表 / CRUD / config_override 解析。"""
import contextlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.models  # noqa: F401  触发全部 mapper 注册（含 ModelCatalog）
from app.models.model_catalog import ModelCatalog


def _seed(db_session):
    db_session.add(ModelCatalog(code="octopus_v1", display_name="章鱼1.0", min_tier="free", credit_price=6, is_active=True, sort_order=0))
    db_session.add(ModelCatalog(code="octopus_v2", display_name="章鱼2.0", min_tier="creator", credit_price=10, is_active=True, sort_order=1))
    db_session.add(ModelCatalog(code="octopus_v3", display_name="章鱼3.0", min_tier="flagship", credit_price=18, is_active=True, sort_order=2))


@pytest.mark.asyncio
async def test_ensure_model_allowed(db_session):
    from app.core.feature_gating import ensure_model_allowed
    _seed(db_session)
    db_session.add(ModelCatalog(code="off", display_name="下架", min_tier="free", credit_price=6, is_active=False))
    await db_session.commit()

    # free 用 v3(flagship) → 403
    with pytest.raises(HTTPException) as ei:
        await ensure_model_allowed(db_session, "octopus_v3", "free")
    assert ei.value.status_code == 403
    # flagship 用 v3 → 放行
    await ensure_model_allowed(db_session, "octopus_v3", "flagship")
    # free 用 v1 → 放行
    await ensure_model_allowed(db_session, "octopus_v1", "free")
    # creator 用 v2 → 放行
    await ensure_model_allowed(db_session, "octopus_v2", "creator")
    # 下架模型 → 403
    with pytest.raises(HTTPException) as ei2:
        await ensure_model_allowed(db_session, "off", "flagship")
    assert ei2.value.status_code == 403
    # 未知 code / 空 → 不阻断(回退默认通道)
    await ensure_model_allowed(db_session, "unknown", "free")
    await ensure_model_allowed(db_session, None, "free")


@pytest.mark.asyncio
async def test_available_models_filter_by_tier(db_session):
    from app.api.routers.model_catalog import list_available_models
    _seed(db_session)
    await db_session.commit()

    res = await list_available_models(db=db_session, current_user=SimpleNamespace(id=100))
    assert res["tier"] == "free"
    assert res["credit"]["balance"] == 60          # free 播种额度
    assert res["polish_price"] == 5                 # 无 SystemConfig 行 → 默认 5
    by_code = {m["code"]: m for m in res["models"]}
    assert by_code["octopus_v1"]["locked"] is False
    assert by_code["octopus_v2"]["locked"] is True  # creator 档，free 锁
    assert by_code["octopus_v3"]["locked"] is True  # flagship 档，free 锁


@pytest.mark.asyncio
async def test_available_models_fallback_defaults(db_session):
    """无模型行时回退 DEFAULT_MODELS（前台仍能展示占位章鱼1.0/2.0/3.0）。"""
    from app.api.routers.model_catalog import list_available_models
    res = await list_available_models(db=db_session, current_user=SimpleNamespace(id=101))
    codes = {m["code"] for m in res["models"]}
    assert {"octopus_v1", "octopus_v2", "octopus_v3"} <= codes


@pytest.mark.asyncio
async def test_crud_create_and_get(db_session):
    from app.api.routers.model_catalog import create_model, get_model_by_code, ModelCatalogPayload
    payload = ModelCatalogPayload(code="newm", display_name="新模型", credit_price=12, min_tier="creator")
    res = await create_model(data=payload, db=db_session, _=None)
    assert res["code"] == "newm" and res["min_tier"] == "creator"
    row = await get_model_by_code(db_session, "newm")
    assert row is not None and row.credit_price == 12
    # 重复 code → 409
    with pytest.raises(HTTPException) as ei:
        await create_model(data=payload, db=db_session, _=None)
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_pipeline_config_threads_model_code(db_session):
    """Phase 3b：flow_config.model_code/enable_polish 须线程进 PipelineConfig（再传到正文 config_override）。"""
    from app.services.pipeline_config_service import PipelineConfigService
    svc = PipelineConfigService(db_session)
    cfg = await svc.resolve_config({"preset": "standard", "model_code": "octopus_v2", "enable_polish": True})
    assert cfg.model_code == "octopus_v2"
    assert cfg.enable_polish is True
    # 不传 model_code → None（用默认通道）
    cfg2 = await svc.resolve_config({"preset": "fast"})
    assert cfg2.model_code is None


@pytest.mark.asyncio
async def test_resolve_config_by_model_code(db_session, monkeypatch):
    from app.services import llm_service as llm_mod
    db_session.add(ModelCatalog(code="m_real", display_name="X", real_model="custom-xyz", min_tier="free", credit_price=6, is_active=True))
    db_session.add(ModelCatalog(code="m_off", display_name="Y", real_model="z", min_tier="free", credit_price=6, is_active=False))
    await db_session.commit()

    @contextlib.asynccontextmanager
    async def fake_factory():
        yield db_session

    monkeypatch.setattr(llm_mod, "AsyncSessionLocal", fake_factory)
    svc = llm_mod.LLMService(session=None)

    cfg = await svc._resolve_config_by_model_code("m_real")
    assert cfg is not None and cfg["model"] == "custom-xyz"   # 用模型行的真实模型
    assert await svc._resolve_config_by_model_code("m_off") is None    # 下架 → None
    assert await svc._resolve_config_by_model_code("nope") is None     # 未知 → None
    assert await svc._resolve_config_by_model_code(None) is None       # 空 → None
