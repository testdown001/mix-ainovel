# AIMETA P=技能API路由|R=技能列表_详情_执行|NR=|E=skill|X=internal|A=技能|D=py|S=net
"""
技能 API 路由

提供技能的列表、详情、执行等接口。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.skill_service import SkillService, SkillInfo
from ...services.writing_skill_registry_service import WritingSkillRegistryService
from ...models import WritingSkillUsage
from ...skills.skill_base import SkillContext

router = APIRouter(prefix="/api/skills", tags=["skills"])


# 响应模型
class SkillInfoResponse(BaseModel):
    """技能信息响应。"""
    id: str
    name: str
    description: str
    version: str
    author: str
    icon: str
    category: str
    trigger: Optional[dict] = None
    capabilities: List[dict]
    config: dict
    scope: Optional[str] = None
    version_id: Optional[int] = None
    status: Optional[str] = None
    execution_mode: Optional[str] = None
    version_snapshot: Optional[dict] = None
    metrics: Optional[dict] = None
    project_id: Optional[str] = None
    base_skill_id: Optional[int] = None
    base_version_id: Optional[int] = None
    is_project_copy: bool = False


class SkillDraftRequest(BaseModel):
    phase: str = "pre_prompt"
    rules: List[str] = Field(default_factory=list)
    prohibitions: List[str] = Field(default_factory=list)
    checker_keys: List[str] = Field(default_factory=list)
    retrieval_hints: List[str] = Field(default_factory=list)
    prompt_hints: List[str] = Field(default_factory=list)
    verify_hints: List[str] = Field(default_factory=list)
    change_note: Optional[str] = None


class SkillPublishRequest(BaseModel):
    version_id: int


class SkillRollbackRequest(BaseModel):
    version_id: int


class SkillFeedbackRequest(BaseModel):
    accepted: bool
    after_score: Optional[float] = Field(default=None, ge=0, le=100)
    feedback: Optional[str] = None


class SkillForkRequest(SkillDraftRequest):
    project_id: str
    name: Optional[str] = None
    description: Optional[str] = None


class SkillExecuteRequest(BaseModel):
    """技能执行请求。"""
    project_id: str
    chapter_number: int
    content: str
    chapter_info: Optional[dict] = Field(default_factory=dict)
    character_profiles: Optional[List[dict]] = Field(default_factory=list)
    world_settings: Optional[dict] = Field(default_factory=dict)
    previous_summary: Optional[str] = ""
    outline: Optional[dict] = Field(default_factory=dict)
    capability_name: Optional[str] = None
    params: Optional[dict] = Field(default_factory=dict)
    user_id: int = Field(default=0)


class SkillExecuteResponse(BaseModel):
    """技能执行响应。"""
    skill_id: str
    capability_name: str
    original_content: str
    transformed_content: str
    success: bool
    error: Optional[str] = None
    metadata: dict
    changed: bool


async def get_skill_service(db: AsyncSession = Depends(get_session)) -> SkillService:
    """获取技能服务实例。"""
    llm_service = LLMService(None)
    return SkillService(llm_service, session=db)


@router.get("", response_model=List[SkillInfoResponse])
async def list_skills(
    category: Optional[str] = None,
    skill_service: SkillService = Depends(get_skill_service)
):
    """列出所有可用技能。"""
    if getattr(skill_service, "session", None) is not None:
        cards = await WritingSkillRegistryService().catalog(skill_service.session)
        if category:
            cards = [item for item in cards if item.get("category") == category]
        return [
            SkillInfoResponse(
                id=item["id"], name=item["name"], description=item["description"],
                version=item.get("version") or "", author="arboris", icon=item.get("icon") or "✨",
                category=item.get("category") or "style", trigger=None,
                capabilities=item.get("capabilities") or [], config=item.get("config") or {},
                scope=item.get("scope"), version_id=item.get("version_id"), status=item.get("status"),
                execution_mode=item.get("execution_mode"), version_snapshot=item.get("version_snapshot"),
                metrics=item.get("metrics"), project_id=item.get("project_id"),
                base_skill_id=item.get("base_skill_id"), base_version_id=item.get("base_version_id"),
                is_project_copy=bool(item.get("is_project_copy")),
            )
            for item in cards
        ]
    if category:
        skills = await skill_service.get_skills_by_category(category)
    else:
        skills = await skill_service.list_skills()

    return [
        SkillInfoResponse(
            id=s.id,
            name=s.name,
            description=s.description,
            version=s.version,
            author=s.author,
            icon=s.icon,
            category=s.category,
            trigger=s.trigger,
            capabilities=s.capabilities,
            config=s.config
        )
        for s in skills
    ]


@router.get("/categories")
async def list_skill_categories(
    skill_service: SkillService = Depends(get_skill_service)
):
    """列出所有技能分类。"""
    categories = await skill_service.list_skill_categories()
    return {"categories": categories}


@router.get("/catalog")
async def list_skill_catalog(
    project_id: Optional[str] = None,
    current_user: Optional[UserInDB] = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """返回当前作者可用的已发布技能卡及效果指标。"""
    if project_id and current_user:
        await NovelService(db).assert_project_owner(project_id, current_user.id)
    registry = WritingSkillRegistryService()
    return await registry.catalog(db, user_id=current_user.id if current_user else None, project_id=project_id)


@router.post("/{skill_id}/project-copy")
async def create_project_skill_copy(
    skill_id: str,
    request: SkillForkRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """为当前小说创建专属技能副本，并以首个已发布版本启用。"""
    await NovelService(db).assert_project_owner(request.project_id, current_user.id)
    data = request.model_dump()
    data.pop("project_id", None)
    try:
        result = await WritingSkillRegistryService().fork_for_project(
            db, skill_id, project_id=request.project_id, user_id=current_user.id, payload=data
        )
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{skill_id}/versions")
async def list_skill_versions(skill_id: str, db: AsyncSession = Depends(get_session)):
    versions = await WritingSkillRegistryService().list_versions(db, skill_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    return {"skill_id": skill_id, "versions": versions}


@router.get("/{skill_id}/metrics")
async def get_skill_metrics(skill_id: str, db: AsyncSession = Depends(get_session)):
    skill = await WritingSkillRegistryService().get_skill(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    return await WritingSkillRegistryService().metrics(db, skill_id)


@router.post("/{skill_id}/versions")
async def create_skill_version(
    skill_id: str,
    request: SkillDraftRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    try:
        data = request.model_dump()
        note = data.pop("change_note", None)
        result = await WritingSkillRegistryService().create_draft(
            db, skill_id, user_id=current_user.id, payload=data, source="author", change_note=note
        )
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{skill_id}/improvement-draft")
async def create_skill_improvement_draft(
    skill_id: str,
    request: SkillDraftRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """创建改进草稿；此接口永远不会自动发布。"""
    data = request.model_dump()
    note = data.pop("change_note", None) or "AI/作者改进建议，待人工审核"
    try:
        result = await WritingSkillRegistryService().create_draft(
            db, skill_id, user_id=current_user.id, payload=data, source="ai_suggestion", change_note=note
        )
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{skill_id}/publish")
async def publish_skill_version(
    skill_id: str,
    request: SkillPublishRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    try:
        result = await WritingSkillRegistryService().publish(
            db, skill_id, request.version_id, user_id=current_user.id, is_admin=current_user.is_admin
        )
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{skill_id}/rollback")
async def rollback_skill_version(
    skill_id: str,
    request: SkillRollbackRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    try:
        result = await WritingSkillRegistryService().rollback(
            db, skill_id, request.version_id, user_id=current_user.id, is_admin=current_user.is_admin
        )
        await db.commit()
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/usages/{usage_id}/feedback")
async def update_skill_usage_feedback(
    usage_id: int,
    request: SkillFeedbackRequest,
    db: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    usage = await db.get(WritingSkillUsage, usage_id)
    if not usage:
        raise HTTPException(status_code=404, detail="使用回执不存在")
    if usage.user_id not in (None, current_user.id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权修改该使用回执")
    usage.accepted = request.accepted
    usage.after_score = request.after_score
    usage.feedback = request.feedback
    await db.commit()
    return {"id": usage.id, "accepted": usage.accepted, "after_score": usage.after_score, "feedback": usage.feedback}


@router.get("/{skill_id}", response_model=SkillInfoResponse)
async def get_skill(
    skill_id: str,
    skill_service: SkillService = Depends(get_skill_service)
):
    """获取技能详情。"""
    skill = await skill_service.get_skill(skill_id)
    if not skill:
        if getattr(skill_service, "session", None) is not None:
            card = next((item for item in await WritingSkillRegistryService().catalog(skill_service.session) if item.get("id") == skill_id), None)
            if card:
                return SkillInfoResponse(
                    id=card["id"], name=card["name"], description=card["description"], version=card.get("version") or "",
                    author="arboris", icon=card.get("icon") or "✨", category=card.get("category") or "style",
                    trigger=None, capabilities=card.get("capabilities") or [], config=card.get("config") or {},
                    scope=card.get("scope"), version_id=card.get("version_id"), status=card.get("status"),
                    execution_mode=card.get("execution_mode"), version_snapshot=card.get("version_snapshot"), metrics=card.get("metrics"),
                )
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    definition = skill.definition
    return SkillInfoResponse(
        id=definition.id,
        name=definition.name,
        description=definition.description,
        version=definition.version,
        author=definition.author,
        icon=definition.icon,
        category=definition.category.value if hasattr(definition.category, 'value') else str(definition.category),
        trigger=definition.trigger,
        capabilities=[
            {"name": cap.name, "description": cap.description}
            for cap in definition.capabilities
        ],
        config={
            "intensity": definition.config.intensity,
            "default": definition.config.default,
            "preserve_original": definition.config.preserve_original
        }
    )


@router.post("/{skill_id}/execute", response_model=SkillExecuteResponse)
async def execute_skill(
    skill_id: str,
    request: SkillExecuteRequest,
    skill_service: SkillService = Depends(get_skill_service),
    db: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """执行技能。"""
    # 归属校验：禁止匿名/越权触发技能执行（否则任意人可反复调用消耗 LLM 费用）
    await NovelService(db).assert_project_owner(request.project_id, current_user.id)

    # 构建上下文：user_id 一律以登录身份为准，忽略请求体自带值
    context = SkillContext(
        project_id=request.project_id,
        chapter_number=request.chapter_number,
        content=request.content,
        chapter_info=request.chapter_info,
        character_profiles=request.character_profiles,
        world_settings=request.world_settings,
        previous_summary=request.previous_summary or "",
        outline=request.outline,
        user_params=request.params,
        metadata={"user_id": current_user.id}
    )

    # 执行技能
    result = await skill_service.execute_skill(
        skill_id=skill_id,
        context=context,
        capability_name=request.capability_name,
        params=request.params
    )

    # 手动变换也写入使用回执，供作者反馈接受/拒绝并形成效果指标。
    usage_id = None
    try:
        resolved = await WritingSkillRegistryService().resolve_selection(
            db, [{"skill_id": skill_id}], project_id=request.project_id, user_id=current_user.id
        )
        version_id = resolved[0].get("version_id") if resolved else None
        usage = await WritingSkillRegistryService().record_usage(
            db,
            skill_key=skill_id,
            version_id=version_id,
            user_id=current_user.id,
            project_id=request.project_id,
            chapter_number=request.chapter_number,
            source="manual_transform",
            changed=result.changed,
            metadata={"capability_name": result.capability_name},
        )
        usage_id = usage.id
        await db.commit()
    except Exception as exc:
        # 指标属于旁路能力，不能让一次已成功的润色变成失败响应。
        await db.rollback()

    metadata = dict(result.metadata or {})
    if usage_id is not None:
        metadata["usage_id"] = usage_id

    return SkillExecuteResponse(
        skill_id=result.skill_id,
        capability_name=result.capability_name,
        original_content=result.original_content,
        transformed_content=result.transformed_content,
        success=result.success,
        error=result.error,
        metadata=metadata,
        changed=result.changed
    )
