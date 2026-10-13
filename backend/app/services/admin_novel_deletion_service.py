"""Admin deletion requires trusted provenance and two typed confirmations."""

import logging
import hashlib
import hmac
import json
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
        await self._delete_projects([project], admin_id)

    async def _get_deletable_projects(self, project_ids: list[str], *, lock: bool = False) -> list[NovelProject]:
        if not project_ids or len(project_ids) > 100 or len(set(project_ids)) != len(project_ids):
            raise HTTPException(status_code=422, detail="每批需选择 1 至 100 个不重复的项目")
        stmt = select(NovelProject).where(NovelProject.id.in_(project_ids)).order_by(NovelProject.id)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        projects = list((await self.session.execute(stmt)).scalars())
        if len(projects) != len(project_ids):
            raise HTTPException(status_code=404, detail="部分项目不存在，请刷新列表后重新确认")
        if any(project.creation_source not in ADMIN_DELETABLE_SOURCES for project in projects):
            raise HTTPException(status_code=403, detail="所选项目包含用户作品或未知来源，整批删除已拒绝")
        return projects

    @staticmethod
    def _batch_fingerprint(projects: list[NovelProject]) -> str:
        records = sorted((project.id, project.user_id, project.creation_source) for project in projects)
        return hashlib.sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest()

    async def confirm_many(self, project_ids: list[str], admin_id: int, confirmation: str) -> AdminNovelDeletionTicket:
        if confirmation != "删除":
            raise HTTPException(status_code=422, detail="请输入“删除”完成第一次确认")
        projects = await self._get_deletable_projects(project_ids)
        now = datetime.now(timezone.utc)
        token = jwt.encode({
            "sub": f"novel-deletion:{admin_id}", "admin_id": admin_id,
            "mode": "batch", "batch_fingerprint": self._batch_fingerprint(projects),
            "aud": _AUDIENCE, "iat": now, "exp": now + timedelta(seconds=_TTL_SECONDS),
        }, _confirmation_key(), algorithm=settings.jwt_algorithm)
        return AdminNovelDeletionTicket(confirmation_token=token, expires_in=_TTL_SECONDS)

    async def delete_many(self, project_ids: list[str], admin_id: int, confirmation: str, token: str) -> None:
        if confirmation != "删除":
            raise HTTPException(status_code=422, detail="请输入“删除”完成第二次确认")
        try:
            claims = jwt.decode(token, _confirmation_key(), algorithms=[settings.jwt_algorithm],
                                audience=_AUDIENCE, options={"require_exp": True})
        except JWTError as exc:
            raise HTTPException(status_code=403, detail="删除确认已失效，请重新完成两次确认") from exc
        if (claims.get("sub") != f"novel-deletion:{admin_id}"
                or claims.get("admin_id") != admin_id or claims.get("mode") != "batch"):
            raise HTTPException(status_code=403, detail="批量删除确认与当前管理员不匹配")
        projects = await self._get_deletable_projects(project_ids, lock=True)
        if claims.get("batch_fingerprint") != self._batch_fingerprint(projects):
            raise HTTPException(status_code=403, detail="所选项目、来源或归属已变更，请重新确认整批项目")
        await self._delete_projects(projects, admin_id)

    async def _delete_projects(self, projects: list[NovelProject], admin_id: int) -> None:
        project_ids = [project.id for project in projects]
        owners = {project.id: project.user_id for project in projects}
        chapter_numbers: dict[str, list[int]] = {project_id: [] for project_id in project_ids}
        for project_id, number in (await self.session.execute(
            select(Chapter.project_id, Chapter.chapter_number).where(Chapter.project_id.in_(project_ids))
        )).all():
            chapter_numbers[project_id].append(number)
        novel_service = NovelService(self.session)
        await novel_service._delete_project_records(projects)
        for project_id in project_ids:
            novel_service._invalidate_chapter_related_cache(project_id)
            if settings.vector_store_enabled:
                await novel_service._delete_chapter_vectors(project_id, chapter_numbers[project_id])
            try:
                await CacheService().invalidate_project_cascade(project_id, owners[project_id])
            except Exception:
                logger.exception("项目已删除，但缓存清理失败: project_id=%s", project_id)
        logger.info("管理员 %s 双重确认删除测试/系统项目：%s", admin_id, project_ids)
