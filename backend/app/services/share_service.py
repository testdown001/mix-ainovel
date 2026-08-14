# AIMETA P=作品公开分享_令牌管理与公开只读视图|R=分享开关_免登录目录与正文|NR=不含注册转化逻辑|E=ShareService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
"""作品公开分享（P2 增长功能）。

设计取舍：
- 令牌即开关：novel_projects.share_token 为 NULL 就是未分享，不加 enabled 布尔列。
  关闭置 NULL、再开启生成新 token——旧链接自然作废，省掉「重新生成」入口。
- 公开视图只暴露已完稿章节（status='successful' 且有 selected_version）：未完稿
  内容、版本列表、蓝图设定、作者 email/user_id 一律不出现在响应里（路由层再用
  显式 Pydantic 白名单兜一层）。
- 无效 token 与未分享统一 404，不泄露项目是否存在。
- author_invite_code 用邀请返积分的自校验码（referral_service.build_invite_code），
  分享页注册 CTA 带上它，把分享转化直接接进邀请奖励闭环——不新增任何表。
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import Chapter, ChapterOutline, ChapterVersion, NovelBlueprint, NovelProject
from ..models.user import User
from . import referral_service

logger = logging.getLogger(__name__)

# 与前端 ChaptersSection 的 generation_status 口径一致：只有 successful 算已完稿
_COMPLETED_STATUS = "successful"
_NOT_FOUND_DETAIL = "分享链接不存在或已失效"


class ShareService:
    """分享开关（owner 侧）与公开只读视图（免登录侧）。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # owner 侧
    # ------------------------------------------------------------------

    async def ensure_share_owner(self, project_id: str, user_id: int) -> NovelProject:
        """分享端点的归属校验：不存在与非属主统一 404（不泄露项目存在性）。

        与 novels.py 其余端点的 ensure_project_owner（非属主 403）口径不同，
        是有意为之——分享功能面向外部传播，枚举 project_id 不该得到任何差异信号。
        """
        project = await self.session.get(NovelProject, project_id)
        if project is None or project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return project

    async def enable_share(self, project: NovelProject) -> str:
        """开启分享：无 token 生成并保存；已有 token 幂等返回现有。"""
        if not project.share_token:
            project.share_token = secrets.token_urlsafe(16)
            await self.session.commit()
            logger.info("项目 %s 开启公开分享", project.id)
        return project.share_token

    async def disable_share(self, project: NovelProject) -> None:
        """关闭分享：置 NULL，旧链接立刻失效。"""
        if project.share_token:
            project.share_token = None
            await self.session.commit()
            logger.info("项目 %s 关闭公开分享", project.id)

    # ------------------------------------------------------------------
    # 公开侧（免登录）
    # ------------------------------------------------------------------

    async def get_public_overview(self, token: str) -> Dict[str, Any]:
        project = await self._resolve_shared_project(token)
        owner = await self.session.get(User, project.user_id)
        blueprint = await self.session.get(NovelBlueprint, project.id)
        chapters = await self._completed_chapters(project.id)
        titles = await self._outline_titles(project.id)
        return {
            "title": project.title,
            "description": blueprint.one_sentence_summary if blueprint else None,
            "author_name": owner.username if owner else "佚名",
            "chapter_count": len(chapters),
            "chapters": [
                {
                    "chapter_number": chapter.chapter_number,
                    "title": titles.get(chapter.chapter_number) or f"第{chapter.chapter_number}章",
                    "word_count": chapter.word_count or 0,
                }
                for chapter in chapters
            ],
            "author_invite_code": referral_service.build_invite_code(project.user_id),
        }

    async def get_public_chapter(self, token: str, chapter_number: int) -> Dict[str, Any]:
        project = await self._resolve_shared_project(token)
        chapters = await self._completed_chapters(project.id)
        target = next((c for c in chapters if c.chapter_number == chapter_number), None)
        if target is None:
            # 未完稿/不存在的章节与无效 token 同语义：404 不作区分
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)

        version = await self.session.get(ChapterVersion, target.selected_version_id)
        if version is None or not version.content:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)

        numbers = [c.chapter_number for c in chapters]
        idx = numbers.index(chapter_number)
        titles = await self._outline_titles(project.id)
        return {
            "chapter_number": chapter_number,
            "title": titles.get(chapter_number) or f"第{chapter_number}章",
            "content": version.content,
            "prev": numbers[idx - 1] if idx > 0 else None,
            "next": numbers[idx + 1] if idx < len(numbers) - 1 else None,
        }

    # ------------------------------------------------------------------
    # 内部查询
    # ------------------------------------------------------------------

    async def _resolve_shared_project(self, token: str) -> NovelProject:
        if not token or len(token) > 64:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        result = await self.session.execute(
            select(NovelProject).where(NovelProject.share_token == token)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)
        return project

    async def _completed_chapters(self, project_id: str) -> List[Chapter]:
        result = await self.session.execute(
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.status == _COMPLETED_STATUS,
                Chapter.selected_version_id.is_not(None),
            )
            .order_by(Chapter.chapter_number)
        )
        return list(result.scalars())

    async def _outline_titles(self, project_id: str) -> Dict[int, str]:
        """章节标题存在大纲表（Chapter 本身无标题列）。"""
        result = await self.session.execute(
            select(ChapterOutline.chapter_number, ChapterOutline.title).where(
                ChapterOutline.project_id == project_id
            )
        )
        return {row[0]: row[1] for row in result.all()}
