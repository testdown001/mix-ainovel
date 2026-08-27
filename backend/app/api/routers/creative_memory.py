# AIMETA P=创作记忆API_候选确认与规则管理|R=鉴权_CRUD_回执查询|NR=不执行LLM学习|E=route:/api/creative-memories/*|X=http|A=REST路由|D=fastapi|S=db
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.creative_memory import (
    CreativeMemoryCreate,
    CreativeMemoryListResponse,
    CreativeMemoryRead,
    CreativeMemoryUpdate,
)
from ...schemas.user import UserInDB
from ...services.creative_memory_service import CreativeMemoryService
from ...services.novel_service import NovelService

router = APIRouter(prefix="/api/creative-memories", tags=["Creative Memories"])


@router.get("/{project_id}", response_model=CreativeMemoryListResponse)
async def list_creative_memories(
    project_id: str,
    chapter_number: Optional[int] = Query(default=None, ge=1),
    memory_status: Optional[str] = Query(default=None, alias="status"),
    scope: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> CreativeMemoryListResponse:
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    service = CreativeMemoryService(session)
    items = await service.list_items(
        user_id=current_user.id,
        project_id=project_id,
        chapter_number=chapter_number,
        status=memory_status,
        scope=scope,
    )
    receipt = None
    if chapter_number is not None:
        receipt = await service.latest_receipt(
            user_id=current_user.id,
            project_id=project_id,
            chapter_number=chapter_number,
        )
    return CreativeMemoryListResponse(
        items=[CreativeMemoryRead.model_validate(item) for item in items],
        latest_receipt=receipt,
        candidate_count=sum(item.status == "candidate" for item in items),
        active_count=sum(item.status == "active" for item in items),
    )


@router.post(
    "/{project_id}",
    response_model=CreativeMemoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_creative_memory(
    project_id: str,
    payload: CreativeMemoryCreate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> CreativeMemoryRead:
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    item = await CreativeMemoryService(session).create_manual(
        user_id=current_user.id,
        project_id=project_id,
        payload=payload,
    )
    return CreativeMemoryRead.model_validate(item)


@router.patch("/{project_id}/{memory_id}", response_model=CreativeMemoryRead)
async def update_creative_memory(
    project_id: str,
    memory_id: int,
    payload: CreativeMemoryUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> CreativeMemoryRead:
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    service = CreativeMemoryService(session)
    item = await service.get_owned_item(
        memory_id=memory_id,
        user_id=current_user.id,
        project_id=project_id,
    )
    if not item:
        raise HTTPException(status_code=404, detail="创作记忆不存在")
    try:
        updated = await service.update_item(item=item, project_id=project_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CreativeMemoryRead.model_validate(updated)


@router.delete("/{project_id}/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_creative_memory(
    project_id: str,
    memory_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Response:
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    service = CreativeMemoryService(session)
    item = await service.get_owned_item(
        memory_id=memory_id,
        user_id=current_user.id,
        project_id=project_id,
    )
    if not item:
        raise HTTPException(status_code=404, detail="创作记忆不存在")
    await service.archive_item(item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
