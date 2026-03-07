# AIMETA P=审查API_六维审查与一致性|R=审查接口|NR=不含生成逻辑|E=route:POST_/api/review/*|X=http|A=审查|D=fastapi,sqlalchemy|S=db|RD=./README.ai
"""审查 API - 六维审查与一致性审核"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.chapter_review import ChapterReview
from ...models.novel import Chapter, ChapterVersion
from ...schemas.user import UserInDB
from ...services.constitution_service import ConstitutionService
from ...services.consistency_service import ConsistencyService
from ...services.gatekeeper_review_service import GatekeeperReviewService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.six_dimension_review_service import SixDimensionReviewService
from ...services.writer_persona_service import WriterPersonaService

router = APIRouter(prefix="/api/review", tags=["Review"])


class SixDimensionReviewRequest(BaseModel):
    project_id: str
    chapter_number: int
    chapter_title: Optional[str] = None
    chapter_content: str
    chapter_plan: Optional[str] = None
    previous_summary: Optional[str] = None
    character_profiles: Optional[str] = None
    world_setting: Optional[str] = None


class ConsistencyReviewRequest(BaseModel):
    project_id: str
    chapter_text: str
    include_foreshadowing: bool = True


@router.post("/six-dimension")
async def review_six_dimension(
    request: SixDimensionReviewRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(request.project_id, current_user.id)

    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    constitution_service = ConstitutionService(session, llm_service, prompt_service)
    persona_service = WriterPersonaService(session, llm_service, prompt_service)
    review_service = SixDimensionReviewService(
        session, llm_service, prompt_service, constitution_service, persona_service
    )

    result = await review_service.review_chapter(
        project_id=request.project_id,
        chapter_number=request.chapter_number,
        chapter_title=request.chapter_title or "",
        chapter_content=request.chapter_content,
        chapter_plan=request.chapter_plan,
        previous_summary=request.previous_summary,
        character_profiles=request.character_profiles,
        world_setting=request.world_setting,
    )
    return {"project_id": request.project_id, "review": result}


@router.post("/consistency")
async def review_consistency(
    request: ConsistencyReviewRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(request.project_id, current_user.id)

    consistency_service = ConsistencyService(session, LLMService(session))
    result = await consistency_service.check_consistency(
        project_id=request.project_id,
        chapter_text=request.chapter_text,
        user_id=current_user.id,
        include_foreshadowing=request.include_foreshadowing,
    )

    report = {
        "is_consistent": result.is_consistent,
        "summary": result.summary,
        "check_time_ms": result.check_time_ms,
        "violations": [
            {
                "severity": v.severity.value if hasattr(v.severity, "value") else v.severity,
                "category": v.category,
                "description": v.description,
                "location": v.location,
                "suggested_fix": v.suggested_fix,
                "confidence": v.confidence,
            }
            for v in result.violations
        ],
    }

    return {"project_id": request.project_id, "review": report}


# ========== 门下省审核 API ==========

class GatekeeperReviewRequest(BaseModel):
    """门下省审核请求"""
    project_id: str
    chapter_number: int
    chapter_version_id: Optional[int] = None  # 指定版本ID，不指定则取最新


class GatekeeperReviewResponse(BaseModel):
    """门下省审核响应"""
    id: int
    project_id: str
    chapter_number: int
    approved: bool
    overall_score: float
    scores: Dict[str, float]
    issues: List[Dict[str, Any]]
    review_comment: Optional[str]
    rewrite_required: bool
    created_at: Any


@router.post("/gatekeeper")
async def review_gatekeeper(
    request: GatekeeperReviewRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """执行门下省章节审核"""
    novel_service = NovelService(session)
    project = await novel_service.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此项目")

    # 获取章节版本
    if request.chapter_version_id:
        from sqlalchemy import select
        stmt = select(ChapterVersion).where(ChapterVersion.id == request.chapter_version_id)
        result = await session.execute(stmt)
        chapter_version = result.scalar_one_or_none()
    else:
        # 获取最新版本
        chapter = await novel_service.get_chapter(request.project_id, request.chapter_number)
        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在")
        if not chapter.versions:
            raise HTTPException(status_code=400, detail="章节没有版本记录")
        chapter_version = chapter.versions[-1]

    # 获取大纲
    outline = None
    try:
        outline = await novel_service.get_chapter_outline(request.project_id, request.chapter_number)
    except Exception:
        pass

    # 执行审核
    review_service = GatekeeperReviewService(session)
    review = await review_service.review_chapter(
        chapter_version=chapter_version,
        project=project,
        outline=outline,
    )

    return {
        "project_id": request.project_id,
        "review": {
            "id": review.id,
            "project_id": review.project_id,
            "chapter_number": review.chapter_number,
            "approved": review.approved,
            "overall_score": review.overall_score,
            "scores": review.scores or {},
            "issues": review.issues or [],
            "review_comment": review.review_comment,
            "rewrite_required": review.rewrite_required,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        }
    }


@router.get("/gatekeeper/{project_id}/{chapter_number}")
async def get_gatekeeper_review(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取章节的门下省审核结果"""
    novel_service = NovelService(session)
    project = await novel_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此项目")

    review_service = GatekeeperReviewService(session)
    review = await review_service.get_review_by_chapter(project_id, chapter_number)

    if not review:
        return {"project_id": project_id, "review": None}

    return {
        "project_id": project_id,
        "review": {
            "id": review.id,
            "project_id": review.project_id,
            "chapter_number": review.chapter_number,
            "approved": review.approved,
            "overall_score": review.overall_score,
            "scores": review.scores or {},
            "issues": review.issues or [],
            "review_comment": review.review_comment,
            "rewrite_required": review.rewrite_required,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        }
    }
