# AIMETA P=写作偏好API_风格配置管理|R=写作偏好CRUD|NR=不含LLM调用|E=route:GET_PUT_DELETE_/api/writing-preferences/*|X=http|A=配置CRUD|D=fastapi,sqlalchemy|S=db|RD=./README.ai
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...core.writing_style_presets import get_preset_list
from ...db.session import get_session
from ...models.user_writing_preference import UserWritingPreference
from ...schemas.user import UserInDB
from ...schemas.writing_preference import (
    PresetInfo,
    WritingPreferenceCreate,
    WritingPreferenceRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/writing-preferences", tags=["Writing Preferences"])


async def _get_preference(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(UserWritingPreference).where(UserWritingPreference.user_id == user_id)
    )
    return result.scalars().first()


@router.get("/presets", response_model=List[PresetInfo])
async def list_presets(
    current_user: UserInDB = Depends(get_current_user),
) -> List[PresetInfo]:
    """列出可选预设风格。"""
    return get_preset_list()


@router.get("", response_model=WritingPreferenceRead)
async def read_writing_preference(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> WritingPreferenceRead:
    pref = await _get_preference(session, current_user.id)
    if not pref:
        raise HTTPException(status_code=404, detail="尚未设置写作偏好")
    return WritingPreferenceRead.model_validate(pref)


@router.put("", response_model=WritingPreferenceRead)
async def upsert_writing_preference(
    payload: WritingPreferenceCreate,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> WritingPreferenceRead:
    pref = await _get_preference(session, current_user.id)
    data = payload.model_dump(exclude_unset=True)
    if pref:
        for key, value in data.items():
            setattr(pref, key, value)
    else:
        pref = UserWritingPreference(user_id=current_user.id, **data)
        session.add(pref)
    await session.commit()
    await session.refresh(pref)
    logger.info("用户 %s 更新写作偏好", current_user.id)
    return WritingPreferenceRead.model_validate(pref)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_writing_preference(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    pref = await _get_preference(session, current_user.id)
    if not pref:
        raise HTTPException(status_code=404, detail="未找到写作偏好")
    await session.delete(pref)
    await session.commit()
    logger.info("用户 %s 删除写作偏好", current_user.id)
