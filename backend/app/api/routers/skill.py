# AIMETA P=技能API路由|R=技能列表_详情_执行|NR=|E=skill|X=internal|A=技能|D=py|S=net
"""
技能 API 路由

提供技能的列表、详情、执行等接口。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...db.session import AsyncSessionLocal
from ...services.llm_service import LLMService
from ...services.skill_service import SkillService, SkillInfo
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


async def get_skill_service() -> SkillService:
    """获取技能服务实例。"""
    llm_service = LLMService(None)
    return SkillService(llm_service)


@router.get("", response_model=List[SkillInfoResponse])
async def list_skills(
    category: Optional[str] = None,
    skill_service: SkillService = Depends(get_skill_service)
):
    """列出所有可用技能。"""
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


@router.get("/{skill_id}", response_model=SkillInfoResponse)
async def get_skill(
    skill_id: str,
    skill_service: SkillService = Depends(get_skill_service)
):
    """获取技能详情。"""
    skill = await skill_service.get_skill(skill_id)
    if not skill:
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
    skill_service: SkillService = Depends(get_skill_service)
):
    """执行技能。"""
    # 构建上下文
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
        metadata={"user_id": request.user_id}
    )

    # 执行技能
    result = await skill_service.execute_skill(
        skill_id=skill_id,
        context=context,
        capability_name=request.capability_name,
        params=request.params
    )

    return SkillExecuteResponse(
        skill_id=result.skill_id,
        capability_name=result.capability_name,
        original_content=result.original_content,
        transformed_content=result.transformed_content,
        success=result.success,
        error=result.error,
        metadata=result.metadata,
        changed=result.changed
    )
