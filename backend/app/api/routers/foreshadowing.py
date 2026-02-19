# AIMETA P=伏笔API_伏笔管理和回收追踪|R=伏笔CRUD_回收追踪|NR=不含自动分析|E=route:GET_POST_/api/foreshadowing/*|X=http|A=伏笔CRUD_回收|D=fastapi,sqlalchemy|S=db|RD=./README.ai
"""伏笔管理 API 接口"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...services.foreshadowing_service import ForeshadowingService
from ...models.foreshadowing import Foreshadowing, ForeshadowingReminder, ForeshadowingAnalysis
from ...models.novel import Chapter, ChapterOutline, NovelProject
from ...core.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/novels", tags=["foreshadowing"])


# Pydantic 模型
from pydantic import BaseModel


class ForeshadowingCreate(BaseModel):
    """创建伏笔请求"""
    chapter_id: int
    chapter_number: int
    content: str
    type: str
    keywords: Optional[List[str]] = None
    author_note: Optional[str] = None


class ForeshadowingResolve(BaseModel):
    """标记伏笔回收请求"""
    resolved_chapter_id: int
    resolved_chapter_number: int
    resolution_text: str
    resolution_type: str = "direct"
    quality_score: Optional[int] = None


class ForeshadowingResponse(BaseModel):
    """伏笔响应"""
    id: int
    project_id: str
    chapter_number: int
    content: str
    type: str
    status: str
    resolved_chapter_number: Optional[int]
    is_manual: bool
    ai_confidence: Optional[float]
    author_note: Optional[str]
    created_at: str


class ReminderResponse(BaseModel):
    """提醒响应"""
    id: int
    foreshadowing_id: int
    reminder_type: str
    message: str
    status: str


class AnalysisResponse(BaseModel):
    """分析响应"""
    total_foreshadowings: int
    resolved_count: int
    unresolved_count: int
    abandoned_count: int
    avg_resolution_distance: Optional[float]
    unresolved_ratio: Optional[float]
    overall_quality_score: Optional[float]
    recommendations: List[str]


class ForeshadowingSummaryItem(BaseModel):
    id: str
    description: str
    planted_chapter: int
    planted_chapter_title: str
    expected_payoff_chapter: Optional[int] = None
    actual_payoff_chapter: Optional[int] = None
    status: str
    importance: str
    urgency: Optional[float] = None
    tier: Optional[str] = None


class ForeshadowingSummaryResponse(BaseModel):
    project_id: str
    project_title: str
    total_foreshadowings: int
    planted_count: int
    paid_off_count: int
    overdue_count: int
    foreshadowings: List[ForeshadowingSummaryItem]


RESOLVED_STATUSES = {"revealed", "resolved", "paid_off", "done", "complete", "completed"}
UNRESOLVED_STATUSES = {"planted", "developing", "partial", "open", "pending", "active"}


def _normalize_status(status: Optional[str]) -> str:
    value = (status or "").strip().lower()
    if value in RESOLVED_STATUSES:
        return "revealed"
    if value == "abandoned":
        return "abandoned"
    if value in UNRESOLVED_STATUSES:
        return "planted"
    return "planted"


def _importance_to_ui(importance: Optional[str]) -> str:
    value = (importance or "").strip().lower()
    if value in {"major", "core", "long"}:
        return "long"
    if value in {"subtle", "decor", "short"}:
        return "short"
    return "medium"


def _importance_to_weight(importance: Optional[str]) -> float:
    value = (importance or "").strip().lower()
    if value in {"major", "core", "long"}:
        return 3.0
    if value in {"subtle", "decor", "short"}:
        return 1.0
    return 2.0


def _importance_to_tier(importance: Optional[str]) -> str:
    value = (importance or "").strip().lower()
    if value in {"major", "core", "long"}:
        return "核心"
    if value in {"subtle", "decor", "short"}:
        return "装饰"
    return "支线"


def _calculate_urgency(
    planted_chapter: int,
    target_chapter: Optional[int],
    current_chapter: int,
    importance: Optional[str],
) -> Optional[float]:
    weight = _importance_to_weight(importance)
    if target_chapter is None:
        return round(weight, 2)
    if target_chapter <= planted_chapter:
        return round(weight * 2.0, 2)
    elapsed = max(0, current_chapter - planted_chapter)
    window = target_chapter - planted_chapter
    return round((elapsed / window) * weight, 2)


@router.post("/{project_id}/foreshadowings", response_model=ForeshadowingResponse)
async def create_foreshadowing(
    project_id: str,
    data: ForeshadowingCreate,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """创建伏笔"""
    try:
        service = ForeshadowingService(session)
        foreshadowing = await service.create_foreshadowing(
            project_id=project_id,
            chapter_id=data.chapter_id,
            chapter_number=data.chapter_number,
            content=data.content,
            foreshadowing_type=data.type,
            keywords=data.keywords,
            author_note=data.author_note,
            is_manual=True,
        )
        await session.commit()
        
        return ForeshadowingResponse(
            id=foreshadowing.id,
            project_id=foreshadowing.project_id,
            chapter_number=foreshadowing.chapter_number,
            content=foreshadowing.content,
            type=foreshadowing.type,
            status=foreshadowing.status,
            resolved_chapter_number=foreshadowing.resolved_chapter_number,
            is_manual=foreshadowing.is_manual,
            ai_confidence=foreshadowing.ai_confidence,
            author_note=foreshadowing.author_note,
            created_at=foreshadowing.created_at.isoformat(),
        )
    except Exception as e:
        logger.exception(f"创建伏笔失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/foreshadowings")
async def list_foreshadowings(
    project_id: str,
    status: Optional[str] = Query(None),
    foreshadowing_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """获取伏笔列表"""
    try:
        service = ForeshadowingService(session)
        foreshadowings, total = await service.get_foreshadowings(
            project_id=project_id,
            status=status,
            foreshadowing_type=foreshadowing_type,
            limit=limit,
            offset=offset,
        )
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "id": f.id,
                    "chapter_number": f.chapter_number,
                    "content": f.content,
                    "type": f.type,
                    "status": f.status,
                    "resolved_chapter_number": f.resolved_chapter_number,
                    "is_manual": f.is_manual,
                    "ai_confidence": f.ai_confidence,
                    "author_note": f.author_note,
                    "created_at": f.created_at.isoformat(),
                }
                for f in foreshadowings
            ],
        }
    except Exception as e:
        logger.exception(f"获取伏笔列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/foreshadowings/summary", response_model=ForeshadowingSummaryResponse)
async def get_foreshadowing_summary(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """获取伏笔管理聚合数据（数据库驱动）。"""
    try:
        project_result = await session.execute(
            select(NovelProject).where(
                NovelProject.id == project_id,
                NovelProject.user_id == current_user.id,
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        service = ForeshadowingService(session)
        foreshadowings, _ = await service.get_foreshadowings(
            project_id=project_id,
            limit=1000,
            offset=0,
        )

        outlines_result = await session.execute(
            select(ChapterOutline.chapter_number, ChapterOutline.title).where(ChapterOutline.project_id == project_id)
        )
        outline_title_map = {
            chapter_number: (title or f"第{chapter_number}章")
            for chapter_number, title in outlines_result.all()
        }

        current_chapter = await session.scalar(
            select(func.max(Chapter.chapter_number)).where(
                Chapter.project_id == project_id,
                Chapter.selected_version_id.is_not(None),
            )
        )
        current_chapter = int(current_chapter or 0)

        planted_count = 0
        paid_off_count = 0
        overdue_count = 0
        items: List[ForeshadowingSummaryItem] = []

        for foreshadowing in foreshadowings:
            normalized_status = _normalize_status(foreshadowing.status)
            if normalized_status == "revealed":
                ui_status = "paid_off"
            else:
                is_overdue = False
                if normalized_status == "abandoned":
                    is_overdue = True
                elif (
                    foreshadowing.target_reveal_chapter
                    and current_chapter > foreshadowing.target_reveal_chapter
                ):
                    is_overdue = True
                ui_status = "overdue" if is_overdue else "planted"

            if ui_status == "paid_off":
                paid_off_count += 1
            elif ui_status == "overdue":
                overdue_count += 1
            else:
                planted_count += 1

            items.append(
                ForeshadowingSummaryItem(
                    id=str(foreshadowing.id),
                    description=foreshadowing.content,
                    planted_chapter=foreshadowing.chapter_number,
                    planted_chapter_title=outline_title_map.get(
                        foreshadowing.chapter_number,
                        f"第{foreshadowing.chapter_number}章",
                    ),
                    expected_payoff_chapter=foreshadowing.target_reveal_chapter,
                    actual_payoff_chapter=foreshadowing.resolved_chapter_number,
                    status=ui_status,
                    importance=_importance_to_ui(foreshadowing.importance),
                    urgency=_calculate_urgency(
                        planted_chapter=foreshadowing.chapter_number,
                        target_chapter=foreshadowing.target_reveal_chapter,
                        current_chapter=current_chapter,
                        importance=foreshadowing.importance,
                    ),
                    tier=_importance_to_tier(foreshadowing.importance),
                )
            )

        items.sort(key=lambda item: (item.planted_chapter, item.id))
        return ForeshadowingSummaryResponse(
            project_id=project_id,
            project_title=project.title,
            total_foreshadowings=len(items),
            planted_count=planted_count,
            paid_off_count=paid_off_count,
            overdue_count=overdue_count,
            foreshadowings=items,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取伏笔汇总失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/foreshadowings/{foreshadowing_id}/resolve")
async def resolve_foreshadowing(
    project_id: str,
    foreshadowing_id: int,
    data: ForeshadowingResolve,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """标记伏笔回收"""
    try:
        service = ForeshadowingService(session)
        resolution = await service.resolve_foreshadowing(
            foreshadowing_id=foreshadowing_id,
            resolved_chapter_id=data.resolved_chapter_id,
            resolved_chapter_number=data.resolved_chapter_number,
            resolution_text=data.resolution_text,
            resolution_type=data.resolution_type,
            quality_score=data.quality_score,
        )
        await session.commit()
        
        return {
            "status": "success",
            "message": "伏笔已标记为回收",
            "resolution_id": resolution.id,
        }
    except Exception as e:
        logger.exception(f"标记伏笔回收失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/foreshadowings/reminders")
async def get_reminders(
    project_id: str,
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """获取伏笔提醒"""
    try:
        service = ForeshadowingService(session)
        reminders = await service.get_active_reminders(project_id=project_id, limit=limit)
        
        return {
            "total": len(reminders),
            "data": [
                {
                    "id": r.id,
                    "foreshadowing_id": r.foreshadowing_id,
                    "reminder_type": r.reminder_type,
                    "message": r.message,
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                }
                for r in reminders
            ],
        }
    except Exception as e:
        logger.exception(f"获取提醒失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/foreshadowings/reminders/{reminder_id}/dismiss")
async def dismiss_reminder(
    project_id: str,
    reminder_id: int,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """忽略提醒"""
    try:
        service = ForeshadowingService(session)
        reminder = await service.dismiss_reminder(reminder_id=reminder_id, reason=reason)
        await session.commit()
        
        return {
            "status": "success",
            "message": "提醒已忽略",
        }
    except Exception as e:
        logger.exception(f"忽略提醒失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/foreshadowings/analysis")
async def get_analysis(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """获取伏笔分析"""
    try:
        service = ForeshadowingService(session)
        analysis = await service.analyze_foreshadowings(project_id=project_id)
        await session.commit()
        
        return {
            "total_foreshadowings": analysis.total_foreshadowings,
            "resolved_count": analysis.resolved_count,
            "unresolved_count": analysis.unresolved_count,
            "abandoned_count": analysis.abandoned_count,
            "avg_resolution_distance": analysis.avg_resolution_distance,
            "unresolved_ratio": analysis.unresolved_ratio,
            "overall_quality_score": analysis.overall_quality_score,
            "recommendations": analysis.recommendations or [],
            "pattern_analysis": analysis.pattern_analysis or {},
            "analyzed_at": analysis.analyzed_at.isoformat(),
        }
    except Exception as e:
        logger.exception(f"获取分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
