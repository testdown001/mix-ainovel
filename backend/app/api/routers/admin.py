# AIMETA P=管理员API_用户管理和系统配置|R=管理员CRUD_系统配置_统计|NR=不含普通用户功能|E=route:POST_GET_/api/admin/*|X=http|A=用户CRUD_配置_统计|D=fastapi,sqlalchemy|S=db|RD=./README.ai
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin
from ...db.session import get_session
from ...models import NovelProject, UsageMetric, User
from ...models.llm_call_log import LLMCallLog
from ...models.payment_order import PaymentOrder
from ...models.plan import Plan
from ...models.user_quota import UserQuota
from ...db.session import AsyncSessionLocal
from ...schemas.admin import (
    AdminNovelSummary,
    DailyRequestLimit,
    Statistics,
    UpdateLogCreate,
    UpdateLogRead,
    UpdateLogUpdate,
)
from ...schemas.config import SystemConfigCreate, SystemConfigRead, SystemConfigUpdate
from ...schemas.prompt import PromptCreate, PromptRead, PromptUpdate
from ...schemas.novel import (
    Chapter as ChapterSchema,
    NovelProject as NovelProjectSchema,
    NovelSectionResponse,
    NovelSectionType,
)
from ...schemas.user import (
    PasswordChangeRequest,
    User as UserSchema,
    UserCreateAdmin,
    UserUpdateAdmin,
)
from ...services.auth_service import AuthService
from ...services.admin_setting_service import AdminSettingService
from ...services.config_service import ConfigService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.quota_service import QuotaService
from ...services.update_log_service import UpdateLogService
from ...services.user_service import UserService
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class AdminUserSummary(UserSchema):
    current_plan_name: str = "免费版"
    premium_expires_at: Optional[str] = None


class UserQuotaSummary(BaseModel):
    is_premium: bool
    plan_tier: str
    effective_tier: str
    premium_expires_at: Optional[str] = None
    daily_chapter_limit: int
    daily_chapter_used: int
    monthly_token_limit: int
    monthly_token_used: int
    storage_limit: int
    storage_used: int


class AdminPlanSummary(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    period: str
    tier: str
    daily_chapter_limit: int
    max_novels: int
    is_active: bool


class UserSubscriptionHistoryItem(BaseModel):
    id: int
    order_no: str
    plan_id: int
    plan_name: str
    amount: float
    currency: str
    channel: str
    status: str
    paid_at: Optional[str] = None
    created_at: Optional[str] = None
    remark: Optional[str] = None


class UserSubscriptionDetail(BaseModel):
    user: UserSchema
    quota: UserQuotaSummary
    current_plan: Optional[AdminPlanSummary] = None
    plans: List[AdminPlanSummary]
    history: List[UserSubscriptionHistoryItem]


class AssignSubscriptionRequest(BaseModel):
    plan_id: int
    period: str = "monthly"
    remark: Optional[str] = None


class ExpiringUserItem(BaseModel):
    user_id: int
    username: str
    email: Optional[str] = None
    plan_tier: str
    effective_tier: str
    premium_expires_at: Optional[str] = None
    days_left: int
    credit_total: int
    has_paid_order: bool
    reminded: bool


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def _tier_label(tier: str) -> str:
    return {
        "free": "免费版",
        "creator": "创作者版",
        "flagship": "旗舰版",
    }.get(tier or "free", tier or "免费版")


def _plan_summary(plan: Plan) -> AdminPlanSummary:
    return AdminPlanSummary(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        price=float(plan.price),
        period=plan.period,
        tier=QuotaService._derive_tier(plan),
        daily_chapter_limit=plan.daily_chapter_limit,
        max_novels=plan.max_novels,
        is_active=plan.is_active,
    )


def _admin_user_summary(
    user: UserSchema,
    quota: Optional[UserQuota],
    plan_by_tier: dict[str, Plan],
) -> AdminUserSummary:
    plan_tier = "free"
    effective_tier = "free"
    premium_expires_at = None
    if quota:
        plan_tier = quota.plan_tier or "free"
        effective_tier = quota.effective_tier
        premium_expires_at = _iso(quota.premium_expires_at)

    current_plan = plan_by_tier.get(effective_tier)
    user_data = UserSchema.model_validate(user).model_dump()
    user_data.update(
        plan_tier=plan_tier,
        effective_tier=effective_tier,
        current_plan_name=current_plan.name if current_plan else _tier_label(effective_tier),
        premium_expires_at=premium_expires_at,
    )
    return AdminUserSummary(
        **user_data,
    )


def get_prompt_service(session: AsyncSession = Depends(get_session)) -> PromptService:
    return PromptService(session)


def get_update_log_service(session: AsyncSession = Depends(get_session)) -> UpdateLogService:
    return UpdateLogService(session)


def get_admin_setting_service(session: AsyncSession = Depends(get_session)) -> AdminSettingService:
    return AdminSettingService(session)


def get_config_service(session: AsyncSession = Depends(get_session)) -> ConfigService:
    return ConfigService(session)


def get_novel_service(session: AsyncSession = Depends(get_session)) -> NovelService:
    return NovelService(session)


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


@router.get("/stats", response_model=Statistics)
async def read_statistics(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_current_admin),
) -> Statistics:
    novel_count = await session.scalar(select(func.count(NovelProject.id))) or 0
    user_count = await session.scalar(select(func.count(User.id))) or 0
    usage = await session.get(UsageMetric, "api_request_count")
    api_request_count = usage.value if usage else 0
    logger.info("管理员获取统计数据：小说=%s，用户=%s，请求=%s", novel_count, user_count, api_request_count)
    return Statistics(novel_count=novel_count, user_count=user_count, api_request_count=api_request_count)


@router.get("/users", response_model=List[AdminUserSummary])
async def list_users(
    session: AsyncSession = Depends(get_session),
    service: UserService = Depends(get_user_service),
    _: None = Depends(get_current_admin),
) -> List[AdminUserSummary]:
    users = await service.list_users()
    user_ids = [user.id for user in users]

    plan_result = await session.execute(select(Plan).order_by(Plan.sort_order, Plan.id))
    plan_by_tier: dict[str, Plan] = {}
    for plan in plan_result.scalars().all():
        plan_by_tier.setdefault(QuotaService._derive_tier(plan), plan)

    quota_by_user_id: dict[int, UserQuota] = {}
    if user_ids:
        quota_result = await session.execute(select(UserQuota).where(UserQuota.user_id.in_(user_ids)))
        quota_by_user_id = {quota.user_id: quota for quota in quota_result.scalars().all()}

    logger.info("管理员请求用户列表，共 %s 条", len(users))
    return [_admin_user_summary(user, quota_by_user_id.get(user.id), plan_by_tier) for user in users]


@router.post("/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateAdmin,
    service: UserService = Depends(get_user_service),
    current_admin=Depends(get_current_admin),
) -> UserSchema:
    try:
        user = await service.create_user_admin(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info("管理员 %s 创建用户：%s", current_admin.username, user.id)
    return UserSchema.model_validate(user)


@router.get("/users/expiring", response_model=List[ExpiringUserItem])
async def list_expiring_users(
    days: int = 7,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_current_admin),
) -> List[ExpiringUserItem]:
    """即将到期的会员，按到期时间升序。

    到期是订阅制唯一的自动流失点：三个渠道都是一次性支付，到期即静默回落 free。
    自动邮件提醒已有（`subscription_reminder_service`），但运营此前无法主动捞人——
    用户列表只能整表翻页，看不出谁快到期了。`has_paid_order` 区分「试用未转化」
    与「付费用户续费」两类完全不同的触达对象；`reminded` 是自动提醒的发送状态，
    避免人工重复打扰。

    路由必须声明在 `/users/{user_id}` 之前，否则 expiring 会被当成 user_id 解析。
    """
    days = max(1, min(days, 90))
    # 与 subscription_reminder_service 同口径用 naive UTC：premium_expires_at 落库是
    # naive，混用 aware 会直接抛 TypeError
    now = datetime.utcnow()
    deadline = now + timedelta(days=days)

    quota_result = await session.execute(
        select(UserQuota)
        .where(
            UserQuota.is_premium.is_(True),
            UserQuota.premium_expires_at.isnot(None),
            UserQuota.premium_expires_at > now,
            UserQuota.premium_expires_at <= deadline,
        )
        .order_by(UserQuota.premium_expires_at)
    )
    quotas = list(quota_result.scalars().all())
    if not quotas:
        return []

    user_ids = [quota.user_id for quota in quotas]
    user_result = await session.execute(select(User).where(User.id.in_(user_ids)))
    user_by_id = {user.id: user for user in user_result.scalars().all()}

    paid_result = await session.execute(
        select(PaymentOrder.user_id)
        .where(PaymentOrder.user_id.in_(user_ids), PaymentOrder.status == "paid")
        .distinct()
    )
    paid_user_ids = {row[0] for row in paid_result.all()}

    items: List[ExpiringUserItem] = []
    for quota in quotas:
        user = user_by_id.get(quota.user_id)
        if not user:
            continue
        expires_at = quota.premium_expires_at
        reference = expires_at.replace(tzinfo=None) if expires_at.tzinfo else expires_at
        items.append(
            ExpiringUserItem(
                user_id=user.id,
                username=user.username,
                email=user.email,
                plan_tier=quota.plan_tier or "free",
                effective_tier=quota.effective_tier,
                premium_expires_at=_iso(expires_at),
                days_left=max(0, (reference - now).days),
                credit_total=quota.credit_total,
                has_paid_order=user.id in paid_user_ids,
                reminded=quota.expiry_reminded_for is not None
                and quota.expiry_reminded_for == quota.premium_expires_at,
            )
        )

    logger.info("管理员请求即将到期用户列表：%s 天内共 %s 人", days, len(items))
    return items


@router.get("/users/{user_id}", response_model=UserSchema)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    _: None = Depends(get_current_admin),
) -> UserSchema:
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserSchema.model_validate(user)


@router.get("/users/{user_id}/subscription", response_model=UserSubscriptionDetail)
async def get_user_subscription(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    service: UserService = Depends(get_user_service),
    _: None = Depends(get_current_admin),
) -> UserSubscriptionDetail:
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    quota_service = QuotaService(session)
    quota = await quota_service.get_or_create_quota(user_id)

    plan_result = await session.execute(select(Plan).order_by(Plan.sort_order, Plan.id))
    plans = list(plan_result.scalars().all())
    current_plan = next(
        (plan for plan in plans if QuotaService._derive_tier(plan) == quota.effective_tier),
        None,
    )

    history_result = await session.execute(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user_id)
        .order_by(desc(PaymentOrder.paid_at), desc(PaymentOrder.created_at), desc(PaymentOrder.id))
        .limit(50)
    )
    history = history_result.scalars().all()

    return UserSubscriptionDetail(
        user=UserSchema.model_validate(user),
        quota=UserQuotaSummary(
            is_premium=quota.is_premium_active,
            plan_tier=quota.plan_tier or "free",
            effective_tier=quota.effective_tier,
            premium_expires_at=_iso(quota.premium_expires_at),
            daily_chapter_limit=quota.daily_chapter_limit,
            daily_chapter_used=quota.daily_chapter_used,
            monthly_token_limit=quota.monthly_token_limit,
            monthly_token_used=quota.monthly_token_used,
            storage_limit=quota.storage_limit,
            storage_used=quota.storage_used,
        ),
        current_plan=_plan_summary(current_plan) if current_plan else None,
        plans=[_plan_summary(plan) for plan in plans],
        history=[
            UserSubscriptionHistoryItem(
                id=order.id,
                order_no=order.order_no,
                plan_id=order.plan_id,
                plan_name=order.plan_name,
                amount=float(order.amount),
                currency=order.currency,
                channel=order.channel,
                status=order.status,
                paid_at=_iso(order.paid_at),
                created_at=_iso(order.created_at),
                remark=order.remark,
            )
            for order in history
        ],
    )


@router.post("/users/{user_id}/subscription", response_model=UserSubscriptionDetail)
async def assign_user_subscription(
    user_id: int,
    payload: AssignSubscriptionRequest,
    session: AsyncSession = Depends(get_session),
    service: UserService = Depends(get_user_service),
    current_admin=Depends(get_current_admin),
) -> UserSubscriptionDetail:
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if payload.period not in {"monthly", "yearly"}:
        raise HTTPException(status_code=400, detail="订阅周期只支持 monthly 或 yearly")

    plan = await session.get(Plan, payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    if not plan.is_active:
        raise HTTPException(status_code=400, detail="套餐已下架，不能分配")
    plan_tier = QuotaService._derive_tier(plan)
    if plan_tier == "free":
        raise HTTPException(status_code=400, detail="免费套餐无需分配订阅")

    days = 365 if payload.period == "yearly" else 30
    expires_at = datetime.utcnow() + timedelta(days=days)

    quota_service = QuotaService(session)
    await quota_service.upgrade_to_premium(user_id, expires_at=expires_at, plan=plan)

    order = PaymentOrder(
        order_no=f"AD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:12].upper()}",
        user_id=user_id,
        plan_id=plan.id,
        plan_name=plan.name,
        amount=0,
        currency="CNY",
        channel="admin",
        status="paid",
        paid_at=datetime.utcnow(),
        remark=payload.remark or f"管理员 {current_admin.username} 分配{days}天订阅",
    )
    session.add(order)
    await session.commit()

    logger.info(
        "管理员 %s 给用户 %s 分配订阅: plan=%s period=%s expires_at=%s",
        current_admin.username,
        user_id,
        plan.id,
        payload.period,
        expires_at,
    )

    return await get_user_subscription(user_id, session, service, current_admin)


@router.patch("/users/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: int,
    payload: UserUpdateAdmin,
    service: UserService = Depends(get_user_service),
    current_admin=Depends(get_current_admin),
) -> UserSchema:
    try:
        user = await service.update_user_admin(user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    logger.info("管理员 %s 更新用户：%s", current_admin.username, user_id)
    return UserSchema.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    current_admin=Depends(get_current_admin),
) -> None:
    try:
        deleted = await service.delete_user(user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="用户不存在")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    logger.info("管理员 %s 删除用户：%s", current_admin.username, user_id)


@router.get("/novel-projects", response_model=List[AdminNovelSummary])
async def list_novel_projects(
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> List[AdminNovelSummary]:
    projects = await service.list_projects_for_admin()
    logger.info("管理员查看项目列表，共 %s 个", len(projects))
    return projects


@router.get("/novel-projects/{project_id}", response_model=NovelProjectSchema)
async def get_novel_project(
    project_id: str,
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> NovelProjectSchema:
    logger.info("管理员查看项目详情：%s", project_id)
    return await service.get_project_schema_for_admin(project_id)


@router.get("/novel-projects/{project_id}/sections/{section}", response_model=NovelSectionResponse)
async def get_novel_project_section(
    project_id: str,
    section: NovelSectionType,
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> NovelSectionResponse:
    logger.info("管理员查看项目 %s 的 %s 区段", project_id, section)
    return await service.get_section_data_for_admin(project_id, section)


@router.get("/novel-projects/{project_id}/chapters/{chapter_number}", response_model=ChapterSchema)
async def get_novel_project_chapter(
    project_id: str,
    chapter_number: int,
    service: NovelService = Depends(get_novel_service),
    _: None = Depends(get_current_admin),
) -> ChapterSchema:
    logger.info("管理员查看项目 %s 第 %s 章详情", project_id, chapter_number)
    return await service.get_chapter_schema_for_admin(project_id, chapter_number)


@router.get("/prompts", response_model=List[PromptRead])
async def list_prompts(
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> List[PromptRead]:
    prompts = await service.list_prompts()
    logger.info("管理员请求提示词列表，共 %s 条", len(prompts))
    return prompts


@router.post("/prompts", response_model=PromptRead, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    payload: PromptCreate,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> PromptRead:
    prompt = await service.create_prompt(payload)
    logger.info("管理员创建提示词：%s", prompt.id)
    return prompt


@router.get("/prompts/{prompt_id}", response_model=PromptRead)
async def get_prompt(
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> PromptRead:
    prompt = await service.get_prompt_by_id(prompt_id)
    if not prompt:
        logger.warning("提示词 %s 不存在", prompt_id)
        raise HTTPException(status_code=404, detail="提示词不存在")
    logger.info("管理员获取提示词：%s", prompt_id)
    return prompt


@router.patch("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: int,
    payload: PromptUpdate,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> PromptRead:
    result = await service.update_prompt(prompt_id, payload)
    if not result:
        logger.warning("提示词 %s 不存在，无法更新", prompt_id)
        raise HTTPException(status_code=404, detail="提示词不存在")
    logger.info("管理员更新提示词：%s", prompt_id)
    return result


@router.post("/prompts/{prompt_id}/reset-to-default", response_model=PromptRead)
async def reset_prompt_to_default(
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> PromptRead:
    """用 prompts/{name}.md 的文件内容覆盖 DB，并让该模板重新跟随文件更新。

    管理员在后台改过的模板会被启动同步视为「已接管」而永不自动覆盖，这是显式回头路。
    """
    result = await service.reset_prompt_to_default(prompt_id)
    if not result:
        logger.warning("提示词 %s 不存在或无对应默认模板文件，无法恢复默认", prompt_id)
        raise HTTPException(status_code=404, detail="提示词不存在或没有对应的默认模板文件")
    logger.info("管理员恢复提示词默认内容：%s", prompt_id)
    return result


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    _: None = Depends(get_current_admin),
) -> None:
    deleted = await service.delete_prompt(prompt_id)
    if not deleted:
        logger.warning("提示词 %s 不存在，无法删除", prompt_id)
        raise HTTPException(status_code=404, detail="提示词不存在")
    logger.info("管理员删除提示词：%s", prompt_id)


@router.get("/update-logs", response_model=List[UpdateLogRead])
async def list_update_logs(
    service: UpdateLogService = Depends(get_update_log_service),
    _: None = Depends(get_current_admin),
) -> List[UpdateLogRead]:
    logs = await service.list_logs()
    logger.info("管理员查看更新日志列表，共 %s 条", len(logs))
    return [UpdateLogRead.model_validate(log) for log in logs]


@router.post("/update-logs", response_model=UpdateLogRead, status_code=status.HTTP_201_CREATED)
async def create_update_log(
    payload: UpdateLogCreate,
    service: UpdateLogService = Depends(get_update_log_service),
    current_admin=Depends(get_current_admin),
) -> UpdateLogRead:
    log = await service.create_log(
        payload.content,
        creator=current_admin.username,
        is_pinned=payload.is_pinned or False,
    )
    logger.info("管理员 %s 创建更新日志：%s", current_admin.username, log.id)
    return UpdateLogRead.model_validate(log)


@router.delete("/update-logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_update_log(
    log_id: int,
    service: UpdateLogService = Depends(get_update_log_service),
    _: None = Depends(get_current_admin),
) -> None:
    await service.delete_log(log_id)
    logger.info("管理员删除更新日志：%s", log_id)


@router.patch("/update-logs/{log_id}", response_model=UpdateLogRead)
async def update_update_log(
    log_id: int,
    payload: UpdateLogUpdate,
    service: UpdateLogService = Depends(get_update_log_service),
    _: None = Depends(get_current_admin),
) -> UpdateLogRead:
    log = await service.update_log(
        log_id,
        content=payload.content,
        is_pinned=payload.is_pinned,
    )
    logger.info("管理员更新日志 %s", log_id)
    return UpdateLogRead.model_validate(log)


@router.get("/settings/daily-request-limit", response_model=DailyRequestLimit)
async def get_daily_limit(
    service: AdminSettingService = Depends(get_admin_setting_service),
    _: None = Depends(get_current_admin),
) -> DailyRequestLimit:
    value = await service.get("daily_request_limit", "100")
    logger.info("管理员查询每日请求上限：%s", value)
    return DailyRequestLimit(limit=int(value or 100))


@router.put("/settings/daily-request-limit", response_model=DailyRequestLimit)
async def update_daily_limit(
    payload: DailyRequestLimit,
    service: AdminSettingService = Depends(get_admin_setting_service),
    _: None = Depends(get_current_admin),
) -> DailyRequestLimit:
    await service.set("daily_request_limit", str(payload.limit))
    logger.info("管理员设置每日请求上限为 %s", payload.limit)
    return payload


@router.get("/system-configs", response_model=List[SystemConfigRead])
async def list_system_configs(
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> List[SystemConfigRead]:
    configs = await service.list_configs()
    logger.info("管理员获取系统配置，共 %s 条", len(configs))
    return configs


@router.get("/system-configs/{key}", response_model=SystemConfigRead)
async def get_system_config(
    key: str,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> SystemConfigRead:
    config = await service.get_config(key)
    if not config:
        logger.warning("系统配置 %s 不存在", key)
        raise HTTPException(status_code=404, detail="配置项不存在")
    logger.info("管理员查询系统配置：%s", key)
    return config


@router.put("/system-configs/{key}", response_model=SystemConfigRead)
async def upsert_system_config(
    key: str,
    payload: SystemConfigCreate,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> SystemConfigRead:
    logger.info("管理员写入系统配置：%s", key)
    return await service.upsert_config(
        SystemConfigCreate(key=key, value=payload.value, description=payload.description)
    )


@router.patch("/system-configs/{key}", response_model=SystemConfigRead)
async def patch_system_config(
    key: str,
    payload: SystemConfigUpdate,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> SystemConfigRead:
    config = await service.patch_config(key, payload)
    if not config:
        logger.warning("系统配置 %s 不存在，无法更新", key)
        raise HTTPException(status_code=404, detail="配置项不存在")
    logger.info("管理员部分更新系统配置：%s", key)
    return config


@router.delete("/system-configs/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_config(
    key: str,
    service: ConfigService = Depends(get_config_service),
    _: None = Depends(get_current_admin),
) -> None:
    deleted = await service.remove_config(key)
    if not deleted:
        logger.warning("系统配置 %s 不存在，无法删除", key)
        raise HTTPException(status_code=404, detail="配置项不存在")
    logger.info("管理员删除系统配置：%s", key)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    current_admin=Depends(get_current_admin),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.change_password(current_admin.username, payload.old_password, payload.new_password)
    logger.info("管理员 %s 修改密码", current_admin.username)


# ------------------------------------------------------------------
# LLM / embedding 通道可用性测试（「测试」按钮）
# ------------------------------------------------------------------

_TESTABLE_CHANNELS = {"default", "fallback", "polish", "search", "grader", "embedding", "rerank"}
# 健康检测覆盖的全部通道（顺序即页面展示顺序）
_HEALTH_CHANNELS = ["default", "fallback", "polish", "search", "grader", "embedding", "rerank"]


class TestChannelRequest(BaseModel):
    channel_type: str  # default | fallback | polish | search | grader | embedding | rerank


@router.post("/test-llm-channel")
async def test_llm_channel(
    payload: TestChannelRequest,
    session: AsyncSession = Depends(get_session),
    _: UserSchema = Depends(get_current_admin),
):
    """真实检测某个已配置的 LLM / embedding 通道是否可用（发起一次最小调用）。"""
    if payload.channel_type not in _TESTABLE_CHANNELS:
        raise HTTPException(status_code=400, detail=f"不支持的通道类型: {payload.channel_type}")
    from ...services.llm_service import LLMService

    llm = LLMService(session)
    result = await llm.test_channel(payload.channel_type)
    logger.info("管理员测试 LLM 通道 %s → ok=%s", payload.channel_type, result.get("ok"))
    return result


# ------------------------------------------------------------------
# LLM 通道诊断（后台「通道诊断」页）
#   GET /llm-health           主动并发检测全部通道实时可用性
#   GET /llm-calls/summary    近期真实调用按通道聚合（错误率/延迟/最近错误）
#   GET /llm-calls            近期真实调用流水（可按通道/状态过滤）
# ------------------------------------------------------------------

_CALL_LOG_WINDOWS = {"1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7}
# summary 聚合的取数上限：超过则只基于「最近 N 条」统计，并在响应里标 truncated=true，
# 避免静默偏移（遥测仅保留 7 天，正常体量远低于此）。
_SUMMARY_ROW_CAP = 20000


@router.get("/llm-health")
async def llm_health(_: UserSchema = Depends(get_current_admin)) -> Dict[str, Any]:
    """并发对所有通道发起一次真实最小调用，返回实时可用性。每个通道用独立 session，
    避免共享请求 session 并发；test_channel 内部已吞掉所有异常，gather 不会失败。"""
    from ...services.llm_service import LLMService

    async def _check(channel: str) -> Dict[str, Any]:
        async with AsyncSessionLocal() as s:
            llm = LLMService(s)
            result = await llm.test_channel(channel)
        return {"channel": channel, **result}

    channels = await asyncio.gather(*[_check(c) for c in _HEALTH_CHANNELS])
    return {"channels": list(channels)}


@router.get("/llm-config-audit")
async def llm_config_audit(
    session: AsyncSession = Depends(get_session),
    _: UserSchema = Depends(get_current_admin),
) -> Dict[str, Any]:
    """只读配置体检：查「实调用测不出」的两类问题——假冗余（兜底与主通道同上游，
    单测都通、上游一挂全挂）与静默失效（嵌入/搜索/评分未配置时相关能力无声跳过）。
    不发任何网络请求，与「通道实时健康」互补。"""
    from ...services.llm_channel_audit import audit_llm_config

    findings = await audit_llm_config(session)
    return {"findings": findings}


def _percentile(values: List[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return int(ordered[idx])


@router.get("/llm-calls/summary")
async def llm_calls_summary(
    window: str = "24h",
    session: AsyncSession = Depends(get_session),
    _: UserSchema = Depends(get_current_admin),
) -> Dict[str, Any]:
    """近期真实 LLM 调用按通道聚合：调用数/成功/错误/超时/错误率/平均·p95·最大延迟/最近错误。"""
    hours = _CALL_LOG_WINDOWS.get(window, 24)
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        await session.execute(
            select(
                LLMCallLog.api_type,
                LLMCallLog.status,
                LLMCallLog.latency_ms,
                LLMCallLog.error_message,
                LLMCallLog.http_status,
                LLMCallLog.created_at,
            )
            .where(LLMCallLog.created_at >= since)
            .order_by(desc(LLMCallLog.created_at))
            .limit(_SUMMARY_ROW_CAP)
        )
    ).all()
    truncated = len(rows) >= _SUMMARY_ROW_CAP

    by_channel: Dict[str, Dict[str, Any]] = {}
    for api_type, status_, latency_ms, error_message, http_status, created_at in rows:
        agg = by_channel.setdefault(
            api_type,
            {
                "channel": api_type,
                "total": 0,
                "success": 0,
                "error": 0,
                "timeout": 0,
                "_latencies": [],
                "last_error": None,
                "last_error_at": None,
                "last_error_http": None,
            },
        )
        agg["total"] += 1
        if status_ in ("success", "error", "timeout"):
            agg[status_] += 1
        agg["_latencies"].append(int(latency_ms or 0))
        # rows 已按时间倒序，首个错误即最近一次错误
        if status_ in ("error", "timeout") and agg["last_error"] is None:
            agg["last_error"] = error_message or status_
            agg["last_error_at"] = created_at.isoformat() if created_at else None
            agg["last_error_http"] = http_status

    channels: List[Dict[str, Any]] = []
    for agg in by_channel.values():
        latencies = agg.pop("_latencies")
        total = agg["total"] or 1
        bad = agg["error"] + agg["timeout"]
        agg["error_rate"] = round(bad / total, 4)
        agg["avg_latency_ms"] = int(sum(latencies) / len(latencies)) if latencies else 0
        agg["p95_latency_ms"] = _percentile(latencies, 95)
        agg["max_latency_ms"] = max(latencies) if latencies else 0
        channels.append(agg)

    channels.sort(key=lambda c: (-c["error_rate"], -c["p95_latency_ms"]))
    return {"window": window, "channels": channels, "truncated": truncated}


@router.get("/llm-calls")
async def llm_calls(
    limit: int = 100,
    channel: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _: UserSchema = Depends(get_current_admin),
) -> Dict[str, Any]:
    """近期真实 LLM 调用流水（默认最近 100 条，可按通道/状态过滤）——排查生成慢时直接看这里。"""
    query = select(LLMCallLog).order_by(desc(LLMCallLog.created_at)).limit(min(max(limit, 1), 500))
    if channel:
        query = query.where(LLMCallLog.api_type == channel)
    if status:
        query = query.where(LLMCallLog.status == status)
    records = (await session.execute(query)).scalars().all()
    return {
        "calls": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "channel": r.api_type,
                "model": r.model,
                "host": r.host,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "http_status": r.http_status,
                "error_type": r.error_type,
                "error_message": r.error_message,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "user_id": r.user_id,
            }
            for r in records
        ]
    }
