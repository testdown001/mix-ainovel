import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...db.session import get_session as get_db
from ...models.plan import Plan
from ...core.dependencies import get_current_admin
from ...core.feature_gating import (
    capabilities_for_tier,
    load_min_tiers,
    registry_dump,
)

router = APIRouter(prefix="/api/plans", tags=["Plans"])


async def _attach_capabilities(plan_dicts: list[dict], db) -> list[dict]:
    """为每个套餐 dict 附加"该档位解锁的能力清单"（与门控同源，自动同步）。"""
    min_tiers = await load_min_tiers(db)
    for pd in plan_dicts:
        pd["capabilities"] = capabilities_for_tier(pd.get("tier", "free") or "free", min_tiers)
    return plan_dicts


class PlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = 0.0
    period: str = "monthly"
    daily_chapter_limit: int = 0
    max_novels: int = 0
    tier: str = "free"  # 订阅档位：free / creator / flagship
    features: Optional[list[str]] = None
    is_recommended: bool = False
    is_active: bool = True
    sort_order: int = 0


class PlanUpdate(PlanCreate):
    pass


def plan_to_dict(plan: Plan) -> dict:
    features = []
    if plan.features:
        try:
            features = json.loads(plan.features)
        except Exception:
            features = []
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "price": plan.price,
        "period": plan.period,
        "daily_chapter_limit": plan.daily_chapter_limit,
        "max_novels": plan.max_novels,
        "tier": getattr(plan, "tier", "free") or "free",
        "features": features,
        "is_recommended": plan.is_recommended,
        "is_active": plan.is_active,
        "sort_order": plan.sort_order,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


DEFAULT_PLANS = [
    {
        "id": "free",
        "name": "免费版",
        "description": "零成本开始创作",
        "price": 0,
        "period": "forever",
        "daily_chapter_limit": 3,
        "max_novels": 2,
        "tier": "free",
        "features": ["每日3章AI辅助", "最多2个项目", "基础灵感系统", "社区支持"],
        "is_recommended": False,
        "is_active": True,
        "sort_order": 0,
    },
    {
        "id": "creator",
        "name": "创作者版",
        "description": "专业作家的必备工具",
        "price": 68,
        "period": "monthly",
        "daily_chapter_limit": 30,
        "max_novels": 20,
        "tier": "creator",
        "features": [
            "每日30章AI辅助",
            "最多20个项目",
            "完整灵感模式",
            "伏笔与世界观系统",
            "自创先进多 Agent 架构",
            "章节质量审核",
            "邮件支持",
        ],
        "is_recommended": True,
        "is_active": True,
        "sort_order": 1,
    },
    {
        "id": "flagship",
        "name": "旗舰版",
        "description": "极限创作力，无拘束表达",
        "price": 128,
        "period": "monthly",
        "daily_chapter_limit": 0,
        "max_novels": 0,
        "tier": "flagship",
        "features": [
            "无限AI章节生成",
            "无限项目数量",
            "完整灵感与世界观系统",
            "全量先进多 Agent 协作",
            "高级章节质量审核",
            "专属写作助理",
            "优先客户支持",
            "新功能抢先体验",
        ],
        "is_recommended": False,
        "is_active": True,
        "sort_order": 2,
    },
]


@router.get("/public")
async def get_public_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order)
    )
    plans = result.scalars().all()
    if not plans:
        return await _attach_capabilities([dict(p) for p in DEFAULT_PLANS], db)
    return await _attach_capabilities([plan_to_dict(p) for p in plans], db)


@router.get("/capabilities")
async def get_capability_registry(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    """能力注册表 + 当前生效最低档位（后台展示"各档位解锁什么"用）。"""
    min_tiers = await load_min_tiers(db)
    return {"capabilities": registry_dump(min_tiers)}


@router.get("/")
async def get_all_plans(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(Plan).order_by(Plan.sort_order))
    plans = result.scalars().all()
    if not plans:
        return await _attach_capabilities([dict(p) for p in DEFAULT_PLANS], db)
    return await _attach_capabilities([plan_to_dict(p) for p in plans], db)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    plan = Plan(
        name=data.name,
        description=data.description,
        price=data.price,
        period=data.period,
        daily_chapter_limit=data.daily_chapter_limit,
        max_novels=data.max_novels,
        tier=data.tier if data.tier in ("free", "creator", "flagship") else "free",
        features=json.dumps(data.features or [], ensure_ascii=False),
        is_recommended=data.is_recommended,
        is_active=data.is_active,
        sort_order=data.sort_order,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan_to_dict(plan)


@router.put("/{plan_id}")
async def update_plan(
    plan_id: int,
    data: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.name = data.name
    plan.description = data.description
    plan.price = data.price
    plan.period = data.period
    plan.daily_chapter_limit = data.daily_chapter_limit
    plan.max_novels = data.max_novels
    if data.tier in ("free", "creator", "flagship"):
        plan.tier = data.tier
    plan.features = json.dumps(data.features or [], ensure_ascii=False)
    plan.is_recommended = data.is_recommended
    plan.is_active = data.is_active
    plan.sort_order = data.sort_order
    await db.commit()
    await db.refresh(plan)
    return plan_to_dict(plan)


@router.patch("/{plan_id}/toggle")
async def toggle_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_active = not plan.is_active
    await db.commit()
    return {"id": plan.id, "is_active": plan.is_active}


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.delete(plan)
    await db.commit()
