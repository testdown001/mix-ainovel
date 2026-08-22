# AIMETA P=参考小说 API 路由_全新 CRUD|R=路由实现|NR=路由合并|E=reference_novels_router|X=http|A=APIRouter|D=fastapi|S=http|RD=./README.ai
from __future__ import annotations

import asyncio
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
from ...services.novel_service import NovelService
from ...services.reference_novel_library_service import ReferenceNovelLibraryService
from ...models import ReferenceNovel

router = APIRouter(prefix="/api/reference-novels", tags=["reference-novels"])
logger = logging.getLogger(__name__)

_analyze_locks: dict[int, asyncio.Lock] = {}
_analyze_locks_guard = asyncio.Lock()


async def _get_analyze_lock(novel_id: int) -> asyncio.Lock:
    async with _analyze_locks_guard:
        if novel_id not in _analyze_locks:
            _analyze_locks[novel_id] = asyncio.Lock()
        return _analyze_locks[novel_id]


async def _background_analyze_reference_novel(novel_id: int, user_id: int) -> None:
    lock = await _get_analyze_lock(novel_id)
    if lock.locked():
        logger.info("参考小说 %d 已有分析任务运行中，跳过", novel_id)
        return
    async with lock:
        async with AsyncSessionLocal() as session:
            service = ReferenceNovelLibraryService(session)
            try:
                novel = await service.get_by_id(novel_id)
                if not novel:
                    return
                if novel.status == "ready":
                    return
                await service.analyze(novel_id, user_id)
            except Exception as exc:  # pragma: no cover
                logger.exception("后台分析参考小说失败: novel_id=%s user_id=%s error=%s", novel_id, user_id, exc)
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
    search: Optional[str] = Query(None, description="在本书参考资料中模糊搜索"),
    project_id: Optional[str] = Query(None, description="当前小说项目 ID"),
    ids: Optional[List[int]] = Query(None, description="尚未创建项目时，当前草稿已选的参考小说 ID"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[ReferenceNovelSummary]:
    """只返回当前小说的参考资料，不暴露账号/系统级全局目录。

    灵感模式在项目创建前使用 ``ids`` 维持当前草稿的最多三本选择；已有项目必须
    使用 ``project_id``，并经过项目所有权校验后从绑定 ID 读取。底层分析记录可以
    继续复用缓存，但产品层的“参考小说库”始终是本书作用域。
    """
    service = ReferenceNovelLibraryService(session)
    if project_id:
        project = await NovelService(session).ensure_project_owner(project_id, current_user.id)
        scoped_ids = list(dict.fromkeys(project.reference_novel_ids or []))[:3]
    else:
        scoped_ids = list(dict.fromkeys(ids or []))[:3]

    if not scoped_ids:
        return []

    novels = await service.get_by_ids(scoped_ids)
    by_id = {novel.id: novel for novel in novels}
    ordered = [by_id[novel_id] for novel_id in scoped_ids if novel_id in by_id]
    normalized_search = (search or "").strip().casefold()
    if normalized_search:
        ordered = [novel for novel in ordered if normalized_search in novel.title.casefold()]
    return [ReferenceNovelSummary.model_validate(novel) for novel in ordered]


@router.post("", response_model=ReferenceNovelSummary, status_code=status.HTTP_201_CREATED)
async def create_reference_novel(
    payload: ReferenceNovelCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ReferenceNovelSummary:
    service = ReferenceNovelLibraryService(session)
    novel = await service.create(
        user_id=current_user.id,
        title=payload.title,
        author=payload.author,
        genre=payload.genre
    )
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
