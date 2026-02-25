# AIMETA P=伏笔API_伏笔管理和回收追踪|R=伏笔CRUD_回收追踪|NR=不含自动分析|E=route:GET_POST_/api/foreshadowing/*|X=http|A=伏笔CRUD_回收|D=fastapi,sqlalchemy|S=db|RD=./README.ai
"""伏笔管理 API 接口"""
import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...services.foreshadowing_service import ForeshadowingService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...models.foreshadowing import Foreshadowing, ForeshadowingReminder, ForeshadowingAnalysis
from ...models.novel import Chapter, ChapterOutline, NovelBlueprint, NovelProject
from ...schemas.novel import ChapterOutline as ChapterOutlineSchema
from ...core.dependencies import get_current_user
from ...utils.json_utils import remove_think_tags, repair_json, sanitize_json_like_text, unwrap_markdown_json

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


class ForeshadowingUpdate(BaseModel):
    """更新伏笔请求"""
    chapter_id: Optional[int] = None
    chapter_number: Optional[int] = None
    content: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    keywords: Optional[List[str]] = None
    author_note: Optional[str] = None
    name: Optional[str] = None
    target_reveal_chapter: Optional[int] = None
    reveal_method: Optional[str] = None
    reveal_impact: Optional[str] = None
    related_characters: Optional[List[str]] = None
    related_plots: Optional[List[str]] = None
    related_foreshadowings: Optional[List[str]] = None
    importance: Optional[str] = None
    urgency: Optional[int] = None
    resolved_chapter_id: Optional[int] = None
    resolved_chapter_number: Optional[int] = None


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
    author_note: Optional[str] = None


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


def _to_foreshadowing_response(foreshadowing: Foreshadowing) -> ForeshadowingResponse:
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

        return _to_foreshadowing_response(foreshadowing)
    except Exception as e:
        logger.exception(f"创建伏笔失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}/foreshadowings/{foreshadowing_id}", response_model=ForeshadowingResponse)
async def update_foreshadowing(
    project_id: str,
    foreshadowing_id: int,
    data: ForeshadowingUpdate,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """更新伏笔"""
    try:
        novel_service = NovelService(session)
        await novel_service.ensure_project_owner(project_id, current_user.id)

        payload = data.model_dump(exclude_unset=True)
        if not payload:
            raise HTTPException(status_code=400, detail="未提供可更新字段")

        service = ForeshadowingService(session)
        foreshadowing = await service.update_foreshadowing(
            project_id=project_id,
            foreshadowing_id=foreshadowing_id,
            data=payload,
        )
        await session.commit()

        return _to_foreshadowing_response(foreshadowing)
    except HTTPException:
        raise
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.exception(f"更新伏笔失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/foreshadowings/{foreshadowing_id}")
async def delete_foreshadowing(
    project_id: str,
    foreshadowing_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """删除伏笔"""
    try:
        novel_service = NovelService(session)
        await novel_service.ensure_project_owner(project_id, current_user.id)

        service = ForeshadowingService(session)
        deleted = await service.delete_foreshadowing(
            project_id=project_id,
            foreshadowing_id=foreshadowing_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="伏笔不存在")

        await session.commit()
        return {"status": "success", "message": "伏笔已删除"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception(f"删除伏笔失败: {e}")
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
                    author_note=foreshadowing.author_note,
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


GENERATE_FORESHADOWINGS_PROMPT = """\
你是一位专业的小说伏笔策划师。请根据以下小说蓝图和章节大纲，为整部小说设计完整的伏笔体系。

## 小说信息
- 标题：{title}
- 类型：{genre}
- 风格：{style}
- 概要：{synopsis}

## 章节大纲
{outlines}

## 要求
1. 设计至少 5 条伏笔，覆盖前期、中期、后期章节
2. 伏笔需形成"埋设→回收"的完整链条
3. 确保 target_chapter >= planted_chapter
4. tier 分为：核心（主线关键伏笔）、支线（次要剧情伏笔）、装饰（氛围细节伏笔）

请以 JSON 数组格式返回，仅返回 JSON，不要其他内容：
[
  {{
    "name": "伏笔名称",
    "description": "伏笔描述",
    "planted_chapter": 1,
    "target_chapter": 10,
    "tier": "核心|支线|装饰",
    "type": "question|mystery|hint|clue|setup",
    "reveal_method": "揭示方式",
    "reveal_impact": "揭示后的影响",
    "related_characters": ["角色名"],
    "related_plots": ["剧情线"]
  }}
]
"""


@router.post("/{project_id}/foreshadowings/generate")
async def generate_foreshadowings(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """基于现有蓝图和大纲，用 AI 生成伏笔数据（不影响蓝图本身）。"""
    # 校验项目归属
    project_result = await session.execute(
        select(NovelProject).where(
            NovelProject.id == project_id,
            NovelProject.user_id == current_user.id,
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 获取蓝图
    blueprint = await session.get(NovelBlueprint, project_id)
    if not blueprint:
        raise HTTPException(status_code=400, detail="项目尚未生成蓝图，请先生成蓝图")

    # 获取章节大纲
    outlines_result = await session.execute(
        select(ChapterOutline)
        .where(ChapterOutline.project_id == project_id)
        .order_by(ChapterOutline.chapter_number)
    )
    outlines = outlines_result.scalars().all()
    if not outlines:
        raise HTTPException(status_code=400, detail="项目没有章节大纲")

    # 大纲太多时采样，避免 prompt 过长
    total = len(outlines)
    if total > 60:
        step = max(1, total // 60)
        sampled = [outlines[i] for i in range(0, total, step)]
        # 确保首尾都在
        if outlines[-1] not in sampled:
            sampled.append(outlines[-1])
        outlines_text = "\n".join(
            f"第{o.chapter_number}章 - {o.title}: {o.summary or '无摘要'}"
            for o in sampled
        )
        outlines_text += f"\n（共{total}章，以上为采样展示）"
    else:
        outlines_text = "\n".join(
            f"第{o.chapter_number}章 - {o.title}: {o.summary or '无摘要'}"
            for o in outlines
        )

    prompt = GENERATE_FORESHADOWINGS_PROMPT.format(
        title=blueprint.title or project.title,
        genre=blueprint.genre or "",
        style=blueprint.style or "",
        synopsis=blueprint.full_synopsis or blueprint.one_sentence_summary or "",
        outlines=outlines_text,
    )

    # 调用 LLM
    llm_service = LLMService(session)
    try:
        raw = await llm_service.get_llm_response(
            system_prompt="你是一位专业的小说伏笔策划师，擅长设计精妙的伏笔体系。",
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=0.8,
            user_id=current_user.id,
            timeout=600.0,
            max_retries=1,
            max_tokens=8192,
        )
    except Exception as e:
        logger.exception("伏笔生成 LLM 调用失败: %s", e)
        raise HTTPException(status_code=500, detail=f"AI 调用失败: {str(e)[:200]}")

    # 解析 JSON
    raw = remove_think_tags(raw)
    cleaned = unwrap_markdown_json(raw)
    cleaned = sanitize_json_like_text(cleaned)
    cleaned = repair_json(cleaned)

    try:
        items = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("伏笔生成 JSON 解析失败: %s\n原始响应末尾: %s", e, raw[-500:])
        raise HTTPException(status_code=500, detail="AI 返回格式异常，请重试")

    if not isinstance(items, list):
        items = items.get("foreshadowings", []) if isinstance(items, dict) else []

    if not items:
        raise HTTPException(status_code=500, detail="AI 未生成有效伏笔数据，请重试")

    # 复用 NovelService 已有的同步逻辑写入数据库
    novel_service = NovelService(session)
    outline_schemas = [
        ChapterOutlineSchema(
            chapter_number=o.chapter_number,
            title=o.title,
            summary=o.summary or "",
        )
        for o in outlines
    ]
    await novel_service._sync_blueprint_foreshadowings(
        project_id=project_id,
        outlines=outline_schemas,
        explicit_items=items,
        prefer_outline_inference=False,
    )
    await session.commit()

    # 返回写入后的数量
    count_result = await session.scalar(
        select(func.count()).select_from(Foreshadowing).where(
            Foreshadowing.project_id == project_id
        )
    )

    return {
        "status": "success",
        "message": f"已生成 {count_result} 条伏笔",
        "total": count_result,
    }
