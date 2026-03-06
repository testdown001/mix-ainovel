# AIMETA P=参考小说 API 路由_全新 CRUD|R=路由实现|NR=路由合并|E=reference_novels_router|X=http|A=APIRouter|D=fastapi|S=http|RD=./README.ai
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal, get_session
from ...schemas.reference_novel import (
    ReferenceNovelCreate,
    ReferenceNovelDetail,
    ReferenceNovelSummary,
    ReferenceNovelUpdate,
)
from ...schemas.user import UserInDB
from ...services.reference_novel_library_service import ReferenceNovelLibraryService
from ...models import ReferenceNovel

router = APIRouter(prefix="/api/reference-novels", tags=["reference-novels"])
logger = logging.getLogger(__name__)


async def _background_analyze_reference_novel(novel_id: int, user_id: int) -> None:
    async with AsyncSessionLocal() as session:
        service = ReferenceNovelLibraryService(session)
        try:
            novel = await service.get_by_id(novel_id)
            if not novel:
                return
            if novel.status == "ready":
                return
            await service.analyze(novel_id, user_id)
        except Exception as exc:  # pragma: no cover - 后台任务兜底
            logger.exception("后台分析参考小说失败: novel_id=%s user_id=%s error=%s", novel_id, user_id, exc)
            # 确保状态回退到 failed，即使 analyze() 内部的异常处理也失败了
            try:
                async with AsyncSessionLocal() as fallback_session:
                    await fallback_session.execute(
                        update(ReferenceNovel)
                        .where(ReferenceNovel.id == novel_id)
                        .values(status="failed", error_message=str(exc)[:500])
                    )
                    await fallback_session.commit()
            except Exception:
                logger.exception("回退参考小说状态也失败: novel_id=%s", novel_id)


@router.get("", response_model=List[ReferenceNovelSummary])
async def list_reference_novels(
    search: Optional[str] = Query(None, description="关键字模糊搜索"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[ReferenceNovelSummary]:
    service = ReferenceNovelLibraryService(session)
    novels = await service.list_all(search=search)
    return [ReferenceNovelSummary.model_validate(novel) for novel in novels]


@router.post("", response_model=ReferenceNovelSummary, status_code=status.HTTP_201_CREATED)
async def create_reference_novel(
    payload: ReferenceNovelCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ReferenceNovelSummary:
    service = ReferenceNovelLibraryService(session)
    novel = await service.create(current_user.id, payload.title)
    if novel.status != "ready":
        background_tasks.add_task(_background_analyze_reference_novel, novel.id, current_user.id)
    return ReferenceNovelSummary.model_validate(novel)


@router.get("/{novel_id}", response_model=ReferenceNovelDetail)
async def get_reference_novel(
    novel_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ReferenceNovelDetail:
    service = ReferenceNovelLibraryService(session)
    novel = await service.get_by_id(novel_id)
    if not novel:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="参考小说不存在")
    return ReferenceNovelDetail.model_validate(novel)


@router.put("/{novel_id}", response_model=ReferenceNovelDetail)
async def update_reference_novel(
    novel_id: int,
    payload: ReferenceNovelUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ReferenceNovelDetail:
    service = ReferenceNovelLibraryService(session)
    data = payload.model_dump(exclude_none=True)
    novel = await service.update(novel_id, current_user, data)
    return ReferenceNovelDetail.model_validate(novel)


@router.delete(
    "/{novel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def delete_reference_novel(
    novel_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Response:
    service = ReferenceNovelLibraryService(session)
    await service.delete(novel_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{novel_id}/analyze", response_model=ReferenceNovelDetail)
async def analyze_reference_novel(
    novel_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ReferenceNovelDetail:
    service = ReferenceNovelLibraryService(session)
    novel = await service.get_by_id(novel_id)
    if not novel:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="参考小说不存在")
    # 立即设置为 analyzing 状态并返回，实际分析在后台执行
    novel.status = "analyzing"
    novel.error_message = None
    await session.commit()
    await session.refresh(novel)
    background_tasks.add_task(_background_analyze_reference_novel, novel_id, current_user.id)
    return ReferenceNovelDetail.model_validate(novel)
