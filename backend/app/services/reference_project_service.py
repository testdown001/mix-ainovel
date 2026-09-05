# AIMETA P=项目参考融合生命周期|R=完整集合检查_过期结果防护|NR=不改绑定|E=refresh_project_fusion|X=internal|A=业务服务|D=sqlalchemy|S=db,net
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from ..models.novel import NovelProject
from .reference_novel_library_service import ReferenceNovelLibraryService
from .reference_reading_contract import is_current, source_signature

logger = logging.getLogger(__name__)
_locks: dict[str, asyncio.Lock] = {}


async def refresh_project_fusion(project_id, expected_ids, user_id, session_factory, *, attempts=1):
    lock = _locks.setdefault(project_id, asyncio.Lock())
    async with lock:
        return await _refresh_project_fusion(project_id, expected_ids, user_id, session_factory, attempts=attempts)


async def _refresh_project_fusion(project_id, expected_ids, user_id, session_factory, *, attempts=1):
    """Read fresh transactions; never save a partial or obsolete book combination."""
    expected_ids = list(dict.fromkeys(expected_ids or []))[:3]
    if not expected_ids:
        return None
    for attempt in range(attempts):
        async with session_factory() as session:
            project = await session.get(NovelProject, project_id)
            if not project or project.user_id != user_id or project.reference_novel_ids != expected_ids:
                return None
            service = ReferenceNovelLibraryService(session)
            novels = await service.get_by_ids(expected_ids)
            if (len(novels) != len(expected_ids)
                    or any(n.status not in {"ready", "pending", "analyzing"} for n in novels)):
                return None
            complete = len(novels) == len(expected_ids) and all(n.status == "ready" for n in novels)
            if complete and is_current(project.fusion_dna, novels, expected_ids):
                return project.fusion_dna
            if complete:
                signature = source_signature(novels)
                dna = await service.generate_fusion_dna(novels, user_id)
        if complete:
            # The LLM call may outlive a rebind or a book reanalysis. Lock only for the final write.
            async with session_factory() as session:
                project = (await session.execute(
                    select(NovelProject).where(NovelProject.id == project_id).with_for_update()
                )).scalar_one_or_none()
                if not project or project.user_id != user_id or project.reference_novel_ids != expected_ids:
                    return None
                current_novels = await ReferenceNovelLibraryService(session).get_by_ids(expected_ids)
                if (len(current_novels) != len(expected_ids)
                        or any(n.status != "ready" for n in current_novels)
                        or source_signature(current_novels) != signature):
                    return None
                if is_current(project.fusion_dna, current_novels, expected_ids):
                    return project.fusion_dna
                project.fusion_dna = dna
                await session.commit()
                return dna
        if attempt + 1 < attempts:
            await asyncio.sleep(15)
    logger.info("参考资料尚未全部就绪，暂缓融合: project=%s ids=%s", project_id, expected_ids)
    return None
