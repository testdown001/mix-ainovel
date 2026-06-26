# AIMETA P=模型目录路由_后台CRUD+前台按档可用列表|R=/api/model-catalog|E=router|X=http|A=路由|D=fastapi,sqlalchemy|S=db
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin, get_current_user
from ...core.feature_gating import tier_rank
from ...db.session import get_session as get_db
from ...models.model_catalog import ModelCatalog
from ...repositories.system_config_repository import SystemConfigRepository
from ...services.quota_service import QuotaService

router = APIRouter(prefix="/api/model-catalog", tags=["ModelCatalog"])

_TIERS = ("free", "creator", "flagship")
_DEFAULT_POLISH_PRICE = 5


class ModelCatalogPayload(BaseModel):
    code: str
    display_name: str
    description: Optional[str] = None
    real_model: Optional[str] = None
    base_url: Optional[str] = None
    api_key_ref: Optional[str] = None
    api_format: Optional[str] = None
    reasoning_effort: Optional[str] = None
    credit_price: int = 10
    min_tier: str = "free"
    is_active: bool = True
    sort_order: int = 0


# 占位默认模型（章鱼1.0/2.0/3.0）：通道五键留空 → 回退 llm.* 默认模型，上线后台再配真实模型。
DEFAULT_MODELS = [
    {"code": "octopus_v1", "display_name": "章鱼1.0", "description": "快速经济，适合走量",
     "credit_price": 6, "min_tier": "free", "is_active": True, "sort_order": 0},
    {"code": "octopus_v2", "display_name": "章鱼2.0", "description": "标准质量，均衡之选",
     "credit_price": 10, "min_tier": "creator", "is_active": True, "sort_order": 1},
    {"code": "octopus_v3", "display_name": "章鱼3.0", "description": "旗舰高质，深度创作",
     "credit_price": 18, "min_tier": "flagship", "is_active": True, "sort_order": 2},
]


def model_to_dict(m: ModelCatalog) -> dict:
    return {
        "id": m.id,
        "code": m.code,
        "display_name": m.display_name,
        "description": m.description,
        "real_model": m.real_model,
        "base_url": m.base_url,
        "api_key_ref": m.api_key_ref,
        "api_format": m.api_format,
        "reasoning_effort": m.reasoning_effort,
        "credit_price": m.credit_price,
        "min_tier": m.min_tier,
        "is_active": m.is_active,
        "sort_order": m.sort_order,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


async def get_model_by_code(session: AsyncSession, code: str) -> Optional[ModelCatalog]:
    """按 code 查模型行（供门控/通道解析复用）。"""
    if not code:
        return None
    result = await session.execute(select(ModelCatalog).where(ModelCatalog.code == code))
    return result.scalar_one_or_none()


async def _polish_price(session: AsyncSession) -> int:
    rec = await SystemConfigRepository(session).get_by_key("credits.price.polish")
    try:
        return int(rec.value) if rec and rec.value is not None else _DEFAULT_POLISH_PRICE
    except (TypeError, ValueError):
        return _DEFAULT_POLISH_PRICE


# ---------------- 前台：按档可用模型 + 我的积分 ----------------

@router.get("/available")
async def list_available_models(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """返回当前用户档位下可见的模型（locked 标记不可用）+ 积分余额 + 润色单价。前台实时拉取。"""
    quota_info = await QuotaService(db).get_quota_info(current_user.id)
    tier = quota_info.get("plan_tier", "free")

    result = await db.execute(
        select(ModelCatalog).where(ModelCatalog.is_active == True).order_by(ModelCatalog.sort_order)
    )
    rows = result.scalars().all()
    models = (
        [model_to_dict(m) for m in rows]
        if rows
        else [dict(m) for m in DEFAULT_MODELS]
    )
    out = [
        {
            "code": m["code"],
            "display_name": m["display_name"],
            "description": m.get("description"),
            "credit_price": m["credit_price"],
            "min_tier": m["min_tier"],
            "locked": tier_rank(tier) < tier_rank(m["min_tier"]),
        }
        for m in models
    ]
    return {
        "tier": tier,
        "credit": quota_info.get("credit", {}),
        "polish_price": await _polish_price(db),
        "models": out,
    }


# ---------------- 后台 CRUD ----------------

@router.get("/")
async def list_models(db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    result = await db.execute(select(ModelCatalog).order_by(ModelCatalog.sort_order))
    rows = result.scalars().all()
    if not rows:
        return [dict(m) for m in DEFAULT_MODELS]
    return [model_to_dict(m) for m in rows]


def _normalize_tier(tier: str) -> str:
    return tier if tier in _TIERS else "free"


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_model(
    data: ModelCatalogPayload,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    exists = await get_model_by_code(db, data.code)
    if exists:
        raise HTTPException(status_code=409, detail=f"模型 code 已存在: {data.code}")
    m = ModelCatalog(
        code=data.code,
        display_name=data.display_name,
        description=data.description,
        real_model=data.real_model or None,
        base_url=data.base_url or None,
        api_key_ref=data.api_key_ref or None,
        api_format=data.api_format or None,
        reasoning_effort=data.reasoning_effort or None,
        credit_price=data.credit_price,
        min_tier=_normalize_tier(data.min_tier),
        is_active=data.is_active,
        sort_order=data.sort_order,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return model_to_dict(m)


@router.put("/{model_id}")
async def update_model(
    model_id: int,
    data: ModelCatalogPayload,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(ModelCatalog).where(ModelCatalog.id == model_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="模型不存在")
    m.code = data.code
    m.display_name = data.display_name
    m.description = data.description
    m.real_model = data.real_model or None
    m.base_url = data.base_url or None
    m.api_key_ref = data.api_key_ref or None
    m.api_format = data.api_format or None
    m.reasoning_effort = data.reasoning_effort or None
    m.credit_price = data.credit_price
    m.min_tier = _normalize_tier(data.min_tier)
    m.is_active = data.is_active
    m.sort_order = data.sort_order
    await db.commit()
    await db.refresh(m)
    return model_to_dict(m)


@router.patch("/{model_id}/toggle")
async def toggle_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(ModelCatalog).where(ModelCatalog.id == model_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="模型不存在")
    m.is_active = not m.is_active
    await db.commit()
    return {"id": m.id, "is_active": m.is_active}


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(ModelCatalog).where(ModelCatalog.id == model_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="模型不存在")
    await db.delete(m)
    await db.commit()
