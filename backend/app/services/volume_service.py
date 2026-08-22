# AIMETA P=M1分卷服务_实体与旧JSON兼容投影|R=分卷同步_章节归属_重规划写入|NR=不含LLM调用|E=VolumeService|X=internal|A=分卷数据收口|D=sqlalchemy|S=db|RD=./README.ai
"""M1 分卷实体服务。

``NovelBlueprint.volumes`` 是既有生成/复盘链路读取的 JSON。M1 引入 ``Volume``
作为持久化事实来源，但保留 JSON 投影，允许当前读路径分阶段迁移，避免一次切换破坏
卷级复盘、发散和生成提示注入。
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.roadmap_metrics import RoadmapMetric, emit_roadmap_metric
from ..models.novel import Chapter, ChapterOutline, NovelBlueprint, Volume

_KNOWN_VOLUME_FIELDS = {
    "id",
    "volume_number",
    "name",
    "start_chapter",
    "end_chapter",
    "arc_goal",
    "climax_hint",
    "status",
    "retrospective",
    "replan",
}


class VolumeService:
    """把分卷 JSON 同步为一等实体，并维护旧链路所需的投影。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def normalize_payload(raw: Any, position: int) -> dict[str, Any] | None:
        """返回可落库的规范卷；非法范围直接跳过，和既有生成读路径一致。"""
        if not isinstance(raw, dict):
            return None
        try:
            start = int(raw.get("start_chapter") or 0)
            end = int(raw.get("end_chapter") or 0)
        except (TypeError, ValueError):
            return None
        if start < 1 or end < start:
            return None
        extra = {key: value for key, value in raw.items() if key not in _KNOWN_VOLUME_FIELDS}
        return {
            "position": position,
            "name": str(raw.get("name") or "").strip(),
            "start_chapter": start,
            "end_chapter": end,
            "arc_goal": str(raw.get("arc_goal") or "").strip() or None,
            "climax_hint": str(raw.get("climax_hint") or "").strip() or None,
            "status": str(raw.get("status") or "planned").strip() or "planned",
            "retrospective": raw.get("retrospective") if isinstance(raw.get("retrospective"), dict) else None,
            "replan": raw.get("replan") if isinstance(raw.get("replan"), dict) else None,
            "extra": extra,
        }

    @staticmethod
    def serialize(record: Volume) -> dict[str, Any]:
        """输出兼容旧 JSON、同时可标识一等实体的分卷 payload。"""
        payload = dict(record.extra or {})
        payload.update(
            {
                "id": record.id,
                "volume_number": record.position,
                "name": record.name or "",
                "start_chapter": record.start_chapter,
                "end_chapter": record.end_chapter,
                "arc_goal": record.arc_goal or "",
                "climax_hint": record.climax_hint or "",
            }
        )
        if record.status and record.status != "planned":
            payload["status"] = record.status
        if record.retrospective:
            payload["retrospective"] = dict(record.retrospective)
        if record.replan:
            payload["replan"] = dict(record.replan)
        return payload

    async def list_records(self, project_id: str) -> list[Volume]:
        result = await self.session.execute(
            select(Volume).where(Volume.project_id == project_id).order_by(Volume.position.asc())
        )
        return list(result.scalars().all())

    async def list_or_backfill(self, project_id: str, *, commit: bool = False) -> list[Volume]:
        records = await self.list_records(project_id)
        if records:
            return records
        blueprint = await self.session.get(NovelBlueprint, project_id)
        if not blueprint or not isinstance(blueprint.volumes, list):
            return []
        records = await self.sync_from_blueprint(blueprint)
        if commit and records:
            await self.session.commit()
        return records

    async def sync_from_blueprint(self, blueprint: NovelBlueprint) -> list[Volume]:
        """把蓝图 JSON 写入实体表，并保留运行期复盘/重规划字段。

        蓝图编辑器通常不会回传 retrospective/replan；缺失时保留实体中的既有值，防止
        作者改一个卷标题把已生效的重规划静默抹掉。
        """
        existing = {record.position: record for record in await self.list_records(blueprint.project_id)}
        normalized: list[dict[str, Any]] = []
        for raw in blueprint.volumes or []:
            item = self.normalize_payload(raw, len(normalized) + 1)
            if item:
                normalized.append(item)

        records: list[Volume] = []
        active_positions: set[int] = set()
        for payload in normalized:
            position = payload["position"]
            active_positions.add(position)
            record = existing.get(position)
            if record is None:
                record = Volume(project_id=blueprint.project_id, position=position)
                self.session.add(record)
            for key in ("name", "start_chapter", "end_chapter", "arc_goal", "climax_hint", "status", "extra"):
                setattr(record, key, payload[key])
            raw = (blueprint.volumes or [])[position - 1]
            if isinstance(raw, dict) and "retrospective" in raw:
                record.retrospective = payload["retrospective"]
            elif record.retrospective is None:
                record.retrospective = payload["retrospective"]
            if isinstance(raw, dict) and "replan" in raw:
                record.replan = payload["replan"]
            elif record.replan is None:
                record.replan = payload["replan"]
            records.append(record)

        for position, stale in existing.items():
            if position not in active_positions:
                await self.session.delete(stale)

        await self.session.flush()
        records.sort(key=lambda item: item.position)
        await self.assign_chapters(blueprint.project_id, records)
        # 反向投影确保旧生成/复盘链路读取到的是与实体一致的内容。
        blueprint.volumes = [self.serialize(record) for record in records]
        emit_roadmap_metric(
            RoadmapMetric.VOLUME_SYNCED,
            project_id=blueprint.project_id,
            volume_count=len(records),
            legacy_backfill=bool(existing == {} and records),
            success=True,
        )
        return records

    async def assign_chapters(self, project_id: str, records: Iterable[Volume] | None = None) -> None:
        """为现有章节和大纲写入卷归属，并为旧数据补稳定排序键。"""
        volumes = list(records) if records is not None else await self.list_records(project_id)

        def _match(chapter_number: int) -> Volume | None:
            return next(
                (
                    volume
                    for volume in volumes
                    if volume.start_chapter <= chapter_number <= volume.end_chapter
                ),
                None,
            )

        outlines_result = await self.session.execute(
            select(ChapterOutline).where(ChapterOutline.project_id == project_id)
        )
        for outline in outlines_result.scalars().all():
            volume = _match(outline.chapter_number)
            outline.volume_id = volume.id if volume else None
            if not outline.sort_key:
                outline.sort_key = outline.chapter_number * 1000

        chapters_result = await self.session.execute(select(Chapter).where(Chapter.project_id == project_id))
        for chapter in chapters_result.scalars().all():
            volume = _match(chapter.chapter_number)
            chapter.volume_id = volume.id if volume else None
            if not chapter.sort_key:
                chapter.sort_key = chapter.chapter_number * 1000

    async def get_by_position(self, project_id: str, position: int) -> Volume | None:
        result = await self.session.execute(
            select(Volume).where(Volume.project_id == project_id, Volume.position == position)
        )
        return result.scalars().first()

    async def update_replan(self, project_id: str, position: int, replan: dict[str, Any]) -> Volume | None:
        record = await self.get_by_position(project_id, position)
        if record is None:
            return None
        record.replan = dict(replan)
        await self._sync_legacy_projection(project_id)
        return record

    async def update_retrospective(
        self, project_id: str, position: int, retrospective: dict[str, Any]
    ) -> Volume | None:
        record = await self.get_by_position(project_id, position)
        if record is None:
            return None
        record.retrospective = dict(retrospective)
        await self._sync_legacy_projection(project_id)
        return record

    async def _sync_legacy_projection(self, project_id: str) -> None:
        blueprint = await self.session.get(NovelBlueprint, project_id)
        if blueprint is None:
            return
        records = await self.list_records(project_id)
        blueprint.volumes = [self.serialize(record) for record in records]
