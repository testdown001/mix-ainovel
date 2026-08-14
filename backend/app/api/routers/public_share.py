# AIMETA P=作品公开分享API_免登录只读|R=分享目录_章节正文|NR=不含分享开关(owner侧在novels.py)|E=route:GET_/api/public/shared/*|X=http|A=公开只读|D=fastapi|S=db|RD=./README.ai
"""作品公开分享的免登录端点。

安全红线：响应模型是显式 Pydantic 白名单（不 model_dump 整个 ORM）——
绝不返回 email、user_id、积分、蓝图设定、未完稿内容、版本列表；
无效 token / 未分享一律 404。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...services.share_service import ShareService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/shared", tags=["PublicShare"])


class SharedChapterMeta(BaseModel):
    chapter_number: int
    title: str
    word_count: int


class SharedNovelOverview(BaseModel):
    title: str
    description: Optional[str] = None
    author_name: str
    chapter_count: int
    chapters: List[SharedChapterMeta]
    # 注册 CTA 带上作者邀请码，把分享转化接进邀请返积分闭环
    author_invite_code: str


class SharedChapterContent(BaseModel):
    chapter_number: int
    title: str
    content: str
    prev: Optional[int] = None
    next: Optional[int] = None


@router.get("/{token}", response_model=SharedNovelOverview)
async def get_shared_novel(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> SharedNovelOverview:
    """分享目录：作品元信息 + 已完稿章节列表（免登录）。"""
    data = await ShareService(session).get_public_overview(token)
    return SharedNovelOverview(**data)


@router.get("/{token}/chapters/{chapter_number}", response_model=SharedChapterContent)
async def get_shared_chapter(
    token: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
) -> SharedChapterContent:
    """章节正文：selected_version 内容 + 相邻已完稿章号（免登录）。"""
    data = await ShareService(session).get_public_chapter(token, chapter_number)
    return SharedChapterContent(**data)
