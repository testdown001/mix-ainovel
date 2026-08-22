# AIMETA P=M1世界状态服务_不可变切片和下一章状态种子|R=状态快照创建_继承读取|NR=不含自动LLM抽取|E=WorldStateService|X=internal|A=世界状态数据服务|D=sqlalchemy|S=db|RD=./README.ai
"""M1 世界状态切片服务。

该服务只管理作者确认、导入或系统明确写入的事实切片。自动 LLM 抽取与跨章诊断属于
M5，不能借 M1 的数据结构绕过作者确认或缺失文本锚点。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.error_codes import DomainErrorCode, api_error
from ..core.roadmap_metrics import RoadmapMetric, emit_roadmap_metric
from ..models.novel import Chapter, ChapterVersion, ChapterWorldState
from ..schemas.world_state import (
    WorldStateSeedResponse,
    WorldStateSlice,
    WorldStateSnapshotCreateRequest,
    WorldStateSnapshotResponse,
)


class WorldStateService:
    """写入不可变状态切片，并为下一章提供最近的确认状态种子。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def source_hash(state: dict[str, Any]) -> str:
        canonical = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def serialize(record: ChapterWorldState) -> WorldStateSnapshotResponse:
        return WorldStateSnapshotResponse(
            id=record.id,
            project_id=record.project_id,
            chapter_number=record.chapter_number,
            source_version_id=record.source_version_id,
            parent_snapshot_id=record.parent_snapshot_id,
            origin=record.origin,
            schema_version=record.schema_version,
            source_hash=record.source_hash,
            state=WorldStateSlice.model_validate(record.state or {}),
            created_at=record.created_at.isoformat() if record.created_at else None,
        )

    async def _chapter_for_project(self, project_id: str, chapter_number: int) -> Chapter:
        result = await self.session.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        chapter = result.scalars().first()
        if chapter is None:
            raise api_error(404, DomainErrorCode.CHAPTER_NOT_FOUND, "未找到指定章节。")
        return chapter

    async def create_snapshot(
        self,
        project_id: str,
        chapter_number: int,
        request: WorldStateSnapshotCreateRequest,
    ) -> ChapterWorldState:
        chapter = await self._chapter_for_project(project_id, chapter_number)
        if request.source_version_id is not None:
            version = await self.session.get(ChapterVersion, request.source_version_id)
            if version is None or version.chapter_id != chapter.id:
                raise api_error(
                    409,
                    DomainErrorCode.WORLD_STATE_SOURCE_MISMATCH,
                    "世界状态引用的版本不属于当前章节。",
                    meta={"chapter_number": chapter_number},
                )

        state_data = request.state.model_dump(mode="json")
        state_hash = self.source_hash(state_data)
        # 一个切片描述的是本章定稿后的状态，因此父节点只能来自此前章节。
        # 同章的多次确认也各自保留，不互相篡改历史证据链。
        parent = await self.latest_before(project_id, chapter_number)
        record = ChapterWorldState(
            project_id=project_id,
            chapter_id=chapter.id,
            chapter_number=chapter_number,
            source_version_id=request.source_version_id,
            parent_snapshot_id=parent.id if parent else None,
            origin=request.origin,
            schema_version=request.state.schema_version,
            state=state_data,
            source_hash=state_hash,
        )
        self.session.add(record)
        await self.session.flush()
        emit_roadmap_metric(
            RoadmapMetric.WORLD_STATE_SNAPSHOT_CREATED,
            project_id=project_id,
            chapter_number=chapter_number,
            version_id=request.source_version_id,
            source=request.origin,
            state_hash=state_hash,
            success=True,
        )
        return record

    async def latest_before(
        self,
        project_id: str,
        target_chapter_number: int,
    ) -> ChapterWorldState | None:
        """读取目标章节之前最近的确认切片；同章时选最后创建的一条。"""
        result = await self.session.execute(
            select(ChapterWorldState)
            .where(
                ChapterWorldState.project_id == project_id,
                ChapterWorldState.chapter_number < target_chapter_number,
            )
            .order_by(ChapterWorldState.chapter_number.desc(), ChapterWorldState.id.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def latest_for_chapter(
        self,
        project_id: str,
        chapter_number: int,
    ) -> ChapterWorldState | None:
        result = await self.session.execute(
            select(ChapterWorldState)
            .where(
                ChapterWorldState.project_id == project_id,
                ChapterWorldState.chapter_number == chapter_number,
            )
            .order_by(ChapterWorldState.id.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def seed_for_chapter(
        self,
        project_id: str,
        target_chapter_number: int,
    ) -> WorldStateSeedResponse:
        source = await self.latest_before(project_id, target_chapter_number)
        emit_roadmap_metric(
            RoadmapMetric.WORLD_STATE_SEED_LOADED,
            project_id=project_id,
            chapter_number=target_chapter_number,
            source_snapshot_id=source.id if source else None,
            success=True,
        )
        return WorldStateSeedResponse(
            target_chapter_number=target_chapter_number,
            source_snapshot_id=source.id if source else None,
            state=WorldStateSlice.model_validate(source.state or {}) if source else None,
        )
