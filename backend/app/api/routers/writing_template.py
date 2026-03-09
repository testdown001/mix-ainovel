# AIMETA P=写作模板API|模板CRUD_应用生成|NR=|E=router|X=http|A=REST_API|D=fastapi|S=net|RD=./README.ai
"""写作模板 API"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.writing_template_service import WritingTemplateService

router = APIRouter(prefix="/api/writing-templates", tags=["WritingTemplate"])


# ============ Schemas ============

class TemplateCreate(BaseModel):
    name: str
    category: str
    prompt_template: str
    description: Optional[str] = None
    icon: Optional[str] = None
    parameters: Optional[List[dict]] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    prompt_template: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    parameters: Optional[List[dict]] = None


class TemplateApplyRequest(BaseModel):
    params: dict


class InferParamsRequest(BaseModel):
    project_id: str
    chapter_number: int


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    description: Optional[str]
    icon: str
    prompt_template: str
    parameters: List[dict]
    use_count: int
    is_builtin: bool


# ============ Routes ============

@router.get("")
async def list_templates(
    category: Optional[str] = None,
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
) -> List[TemplateResponse]:
    """列出所有写作模板"""
    service = WritingTemplateService(session)
    templates = await service.list_templates(category=category, search=search)
    return [TemplateResponse(**t.to_dict() if hasattr(t, 'to_dict') else t) for t in templates]


@router.get("/categories")
async def get_categories(
    session: AsyncSession = Depends(get_session)
) -> List[dict]:
    """获取所有模板分类"""
    service = WritingTemplateService(session)
    return service.get_categories()


@router.get("/{template_id}")
async def get_template(
    template_id: int,
    session: AsyncSession = Depends(get_session)
) -> TemplateResponse:
    """获取单个模板详情"""
    service = WritingTemplateService(session)
    template = await service.get_template(template_id)

    if not template:
        # 尝试从内置模板获取
        from ...models.writing_template import BUILTIN_TEMPLATES
        builtin = next((t for t in BUILTIN_TEMPLATES if t["name"] == str(template_id)), None)
        if builtin:
            return TemplateResponse(
                id=-1,
                name=builtin["name"],
                category=builtin["category"],
                description=builtin.get("description"),
                icon=builtin.get("icon", "📝"),
                prompt_template=builtin["prompt_template"],
                parameters=builtin.get("parameters", []),
                use_count=0,
                is_builtin=True
            )
        raise HTTPException(status_code=404, detail="模板不存在")

    return TemplateResponse(**template.to_dict())


@router.post("")
async def create_template(
    template: TemplateCreate,
    session: AsyncSession = Depends(get_session)
) -> TemplateResponse:
    """创建新的写作模板"""
    service = WritingTemplateService(session)
    new_template = await service.create_template(
        name=template.name,
        category=template.category,
        prompt_template=template.prompt_template,
        description=template.description,
        icon=template.icon,
        parameters=template.parameters
    )
    return TemplateResponse(**new_template.to_dict())


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    template: TemplateUpdate,
    session: AsyncSession = Depends(get_session)
) -> TemplateResponse:
    """更新写作模板"""
    service = WritingTemplateService(session)
    update_data = template.model_dump(exclude_unset=True)
    updated = await service.update_template(template_id, **update_data)
    return TemplateResponse(**updated.to_dict())


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    session: AsyncSession = Depends(get_session)
) -> dict:
    """删除写作模板"""
    service = WritingTemplateService(session)
    await service.delete_template(template_id)
    return {"message": "模板已删除"}


@router.post("/{template_id}/apply")
async def apply_template(
    template_id: int,
    request: TemplateApplyRequest,
    session: AsyncSession = Depends(get_session)
) -> dict:
    """应用模板，生成最终 prompt"""
    service = WritingTemplateService(session)
    prompt = await service.apply_template(template_id, request.params)
    return {"prompt": prompt}


@router.post("/{template_id}/infer-params")
async def infer_template_params(
    template_id: int,
    request: InferParamsRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """AI 推演模板参数值"""
    service = WritingTemplateService(session)
    params = await service.infer_params(
        template_id=template_id,
        project_id=request.project_id,
        chapter_number=request.chapter_number,
        user_id=current_user.id,
    )
    return {"params": params}
