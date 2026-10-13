"""Admin deletion requires trusted provenance and two typed confirmations."""

import logging
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.project_source import ADMIN_DELETABLE_SOURCES
from ..models.novel import Chapter, NovelProject
from ..schemas.admin import AdminNovelDeletionTicket
from .cache_service import CacheService
from .novel_service import NovelService

logger = logging.getLogger(__name__)
_AUDIENCE = "admin-novel-delete"
_TTL_SECONDS = 300


def _confirmation_key() -> str:
    # Separate signing domain: a confirmation ticket must never authenticate a user.
    return hmac.new(settings.secret_key.encode(), b"admin-novel-deletion", hashlib.sha256).hexdigest()


class AdminNovelDeletionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_deletable_project(self, project_id: str, *, lock: bool = False) -> NovelProject:
        stmt = select(NovelProject).where(NovelProject.id == project_id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        project = (await self.session.execute(stmt)).scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        if project.creation_source not in ADMIN_DELETABLE_SOURCES:
            raise HTTPException(status_code=403, detail="后台仅可删除系统或 AI 测试项目，用户作品受保护")
        return project

    async def confirm(self, project_id: str, admin_id: int, confirmation: str) -> AdminNovelDeletionTicket:
        if confirmation != "删除":
            raise HTTPException(status_code=422, detail="请输入“删除”完成第一次确认")
        project = await self._get_deletable_project(project_id)
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                # This subject cannot be used as a login access token.
                "sub": f"novel-deletion:{admin_id}",
                "admin_id": admin_id,
                "project_id": project.id,
                "owner_id": project.user_id,
                "creation_source": project.creation_source,
                "aud": _AUDIENCE,
                "iat": now,
                "exp": now + timedelta(seconds=_TTL_SECONDS),
            },
            _confirmation_key(),
            algorithm=settings.jwt_algorithm,
        )
        return AdminNovelDeletionTicket(confirmation_token=token, expires_in=_TTL_SECONDS)

    async def delete(self, project_id: str, admin_id: int, confirmation: str, token: str) -> None:
        if confirmation != "删除":
            raise HTTPException(status_code=422, detail="请输入“删除”完成第二次确认")
        try:
            claims = jwt.decode(
                token, _confirmation_key(), algorithms=[settings.jwt_algorithm],
                audience=_AUDIENCE, options={"require_exp": True},
            )
        except JWTError as exc:
            raise HTTPException(status_code=403, detail="删除确认已失效，请重新完成两次确认") from exc
        if (
            claims.get("sub") != f"novel-deletion:{admin_id}"
            or claims.get("admin_id") != admin_id
            or claims.get("project_id") != project_id
        ):
            raise HTTPException(status_code=403, detail="删除确认与当前管理员或项目不匹配")
        project = await self._get_deletable_project(project_id, lock=True)
        if (
            claims.get("creation_source") != project.creation_source
            or claims.get("owner_id") != project.user_id
        ):
            raise HTTPException(status_code=403, detail="项目来源或归属已变更，请重新确认")
        owner_id = project.user_id
        chapter_numbers = list((await self.session.execute(
            select(Chapter.chapter_number).where(Chapter.project_id == project_id)
        )).scalars())
        # Reuse the existing transactional cascade and post-commit cover cleanup.
        novel_service = NovelService(self.session)
        await novel_service.delete_projects([project_id], owner_id)
        novel_service._invalidate_chapter_related_cache(project_id)
        if settings.vector_store_enabled:
            await novel_service._delete_chapter_vectors(project_id, chapter_numbers)
        try:
            await CacheService().invalidate_project_cascade(project_id, owner_id)
        except Exception:
            logger.exception("项目已删除，但缓存清理失败: project_id=%s", project_id)
        logger.info("管理员 %s 双重确认删除测试/系统项目：%s", admin_id, project_id)
