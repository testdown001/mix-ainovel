# AIMETA P=小说服务_小说管理业务逻辑|R=小说CRUD_章节管理|NR=不含内容生成|E=NovelService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

_PREFERRED_CONTENT_KEYS: tuple[str, ...] = (
    "content",
    "chapter_content",
    "chapter_text",
    "full_content",
    "text",
    "body",
    "story",
    "chapter",
    "real_summary",
    "summary",
)

_FORESHADOWING_TIER_WEIGHTS: dict[str, float] = {
    "core": 3.0,
    "sub": 2.0,
    "decor": 1.0,
}
_FORESHADOWING_DEFAULT_WINDOWS: dict[str, int] = {
    "core": 120,
    "sub": 60,
    "decor": 20,
}
_FORESHADOWING_HINT_KEYWORDS: tuple[str, ...] = (
    "伏笔",
    "暗示",
    "悬念",
    "谜团",
    "秘密",
    "诡异",
    "真相",
    "线索",
    "疑点",
)
_FORESHADOWING_CORE_HINTS: tuple[str, ...] = ("主线", "终极", "身世", "幕后", "真相", "宿命", "核心")
_FORESHADOWING_DECOR_HINTS: tuple[str, ...] = ("细节", "小事", "日常", "装饰", "习惯")

_chapter_record_locks: dict[tuple[str, int], asyncio.Lock] = {}
_chapter_record_locks_guard = asyncio.Lock()


async def _get_chapter_record_lock(project_id: str, chapter_number: int) -> asyncio.Lock:
    key = (project_id, chapter_number)
    async with _chapter_record_locks_guard:
        lock = _chapter_record_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _chapter_record_locks[key] = lock
        return lock


def _has_meaningful_chapter_status(status_value: Optional[str]) -> bool:
    normalized = (status_value or "").strip()
    return normalized not in ("", "not_generated")


def _chapter_completeness_sort_key(chapter: Any) -> tuple[int, int, int, int, int, int]:
    versions = getattr(chapter, "versions", None) or []
    evaluations = getattr(chapter, "evaluations", None) or []
    return (
        1 if getattr(chapter, "selected_version_id", None) else 0,
        len(versions),
        1 if getattr(chapter, "real_summary", None) else 0,
        1 if _has_meaningful_chapter_status(getattr(chapter, "status", None)) else 0,
        1 if (getattr(chapter, "word_count", 0) or 0) > 0 else 0,
        -(getattr(chapter, "id", 0) or 0),
    )


def _select_canonical_chapter(chapters: Iterable[Any]) -> Any:
    return max(chapters, key=_chapter_completeness_sort_key)


def _collapse_chapters_by_number(chapters: Iterable[Any]) -> Dict[int, Any]:
    chapter_map: Dict[int, Any] = {}
    for chapter in chapters or []:
        existing = chapter_map.get(chapter.chapter_number)
        if existing is None or _chapter_completeness_sort_key(chapter) > _chapter_completeness_sort_key(existing):
            chapter_map[chapter.chapter_number] = chapter
    return chapter_map


def _normalize_version_content(raw_content: Any, metadata: Any) -> str:
    # 版本正文只能来自显式 content；metadata 是调试/追踪信息，不能兜底成正文。
    text = _coerce_text(raw_content)
    return text or ""


def _coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in _PREFERRED_CONTENT_KEYS:
            if key in value and value[key]:
                nested = _coerce_text(value[key])
                if nested:
                    return nested
        return _clean_string(json.dumps(value, ensure_ascii=False), parse_json=False)
    if isinstance(value, (list, tuple, set)):
        parts = [text for text in (_coerce_text(item) for item in value) if text]
        if parts:
            return "\n".join(parts)
        return None
    return _clean_string(str(value))


def _clean_string(text: str, parse_json: bool = True) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if parse_json and (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        try:
            parsed = json.loads(stripped)
            coerced = _coerce_text(parsed)
            if coerced:
                return coerced
        except json.JSONDecodeError:
            pass
    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        stripped = stripped[1:-1]
    return (
        stripped.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )

from fastapi import HTTPException, status
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    BlueprintCharacter,
    BlueprintRelationship,
    Chapter,
    ChapterEvaluation,
    ChapterOutline,
    ChapterVersion,
    Foreshadowing,
    ForeshadowingResolution,
    NovelBlueprint,
    NovelConversation,
    NovelProject,
)
from ..models.entity_registry import EntityRegistry
from ..models.faction import Faction
from ..repositories.novel_repository import NovelRepository
from ..schemas.admin import AdminNovelSummary
from ..schemas.novel import (
    Blueprint,
    BlueprintForeshadowing,
    Chapter as ChapterSchema,
    ChapterGenerationStatus,
    ChapterOutline as ChapterOutlineSchema,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
)
from ..services.cache_service import CacheService
from ..services.chapter_ingest_service import ChapterIngestionService
from ..services.llm_service import LLMService

logger = logging.getLogger(__name__)

_RESOLVED_FORESHADOWING_STATUSES: tuple[str, ...] = (
    "revealed",
    "resolved",
    "paid_off",
    "done",
    "complete",
    "completed",
)


class NovelService:
    """小说项目服务，基于拆表后的结构提供聚合与业务操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NovelRepository(session)

    # ------------------------------------------------------------------
    # 项目与摘要
    # ------------------------------------------------------------------
    async def create_project(self, user_id: int, title: str, initial_prompt: str) -> NovelProject:
        project = NovelProject(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            initial_prompt=initial_prompt,
        )
        blueprint = NovelBlueprint(project=project)
        self.session.add_all([project, blueprint])
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def ensure_project_owner(self, project_id: str, user_id: int) -> NovelProject:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if project.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
        return project

    async def assert_project_owner(self, project_id: str, user_id: int) -> None:
        """轻量归属校验：只查 user_id 一列，不全量加载整本小说。

        用于只需鉴权、不需要项目完整数据的调用点（如世界观子资源增删改）；
        需要完整 NovelProject 的调用方仍用 ensure_project_owner。
        """
        owner_id = await self.repo.get_owner_id(project_id)
        if owner_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if owner_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")

    async def get_project_schema(self, project_id: str, user_id: int) -> NovelProjectSchema:
        project = await self.ensure_project_owner(project_id, user_id)
        return await self._serialize_project(project)

    async def set_completed(self, project_id: str, user_id: int, is_completed: bool) -> None:
        project = await self.ensure_project_owner(project_id, user_id)
        project.is_completed = is_completed
        await self.session.commit()
        await self._touch_project(project_id)

    async def get_section_data(
        self,
        project_id: str,
        user_id: int,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        project = await self.ensure_project_owner(project_id, user_id)
        return self._build_section_response(project, section)

    async def get_chapter_schema(
        self,
        project_id: str,
        user_id: int,
        chapter_number: int,
    ) -> ChapterSchema:
        project = await self.ensure_project_owner(project_id, user_id)
        return self._build_chapter_schema(project, chapter_number)

    async def list_projects_for_user(self, user_id: int) -> List[NovelProjectSummary]:
        projects = await self.repo.list_by_user(user_id)
        summaries: List[NovelProjectSummary] = []
        for project in projects:
            blueprint = project.blueprint
            genre = blueprint.genre if blueprint and blueprint.genre else "未知"
            outlines = project.outlines
            chapters = project.chapters
            total = len(outlines) or len(chapters)
            completed = sum(1 for chapter in chapters if chapter.selected_version_id)
            summaries.append(
                NovelProjectSummary(
                    id=project.id,
                    title=project.title,
                    genre=genre,
                    last_edited=project.updated_at.isoformat() if project.updated_at else "未知",
                    completed_chapters=completed,
                    total_chapters=total,
                    is_completed=bool(project.is_completed),
                )
            )
        return summaries

    async def list_projects_for_admin(self) -> List[AdminNovelSummary]:
        projects = await self.repo.list_all()
        summaries: List[AdminNovelSummary] = []
        for project in projects:
            blueprint = project.blueprint
            genre = blueprint.genre if blueprint and blueprint.genre else "未知"
            outlines = project.outlines
            chapters = project.chapters
            total = len(outlines) or len(chapters)
            completed = sum(1 for chapter in chapters if chapter.selected_version_id)
            owner = project.owner
            summaries.append(
                AdminNovelSummary(
                    id=project.id,
                    title=project.title,
                    owner_id=owner.id if owner else 0,
                    owner_username=owner.username if owner else "未知",
                    genre=genre,
                    last_edited=project.updated_at.isoformat() if project.updated_at else "",
                    completed_chapters=completed,
                    total_chapters=total,
                )
            )
        return summaries

    async def delete_projects(self, project_ids: List[str], user_id: int) -> None:
        for pid in project_ids:
            project = await self.ensure_project_owner(pid, user_id)
            await self.repo.delete(project)
        await self.session.commit()

    async def count_projects(self) -> int:
        result = await self.session.execute(select(func.count(NovelProject.id)))
        return result.scalar_one()

    async def count_user_projects_today(self, user_id: int) -> int:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(func.count())
            .select_from(NovelProject)
            .where(NovelProject.user_id == user_id, NovelProject.created_at >= today_start)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # 对话管理
    # ------------------------------------------------------------------
    async def list_conversations(self, project_id: str) -> List[NovelConversation]:
        stmt = (
            select(NovelConversation)
            .where(NovelConversation.project_id == project_id)
            .order_by(NovelConversation.seq.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def append_conversation(self, project_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        result = await self.session.execute(
            select(func.max(NovelConversation.seq)).where(NovelConversation.project_id == project_id)
        )
        current_max = result.scalar()
        next_seq = (current_max or 0) + 1
        convo = NovelConversation(
            project_id=project_id,
            seq=next_seq,
            role=role,
            content=content,
            metadata=metadata,
        )
        self.session.add(convo)
        await self.session.commit()
        await self._touch_project(project_id)

    # ------------------------------------------------------------------
    # 蓝图管理
    # ------------------------------------------------------------------
    async def replace_blueprint(self, project_id: str, blueprint: Blueprint) -> None:
        existing_outline_metadata = await self._get_outline_metadata_map(project_id)

        record = await self.session.get(NovelBlueprint, project_id)
        if not record:
            record = NovelBlueprint(project_id=project_id)
            self.session.add(record)
        record.title = blueprint.title
        record.target_audience = blueprint.target_audience
        record.genre = blueprint.genre
        record.style = blueprint.style
        record.tone = blueprint.tone
        record.one_sentence_summary = blueprint.one_sentence_summary
        record.full_synopsis = blueprint.full_synopsis
        record.world_setting = blueprint.world_setting
        record.golden_finger = blueprint.golden_finger

        await self.session.execute(delete(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id))
        if blueprint.characters:
            await self.session.execute(
                BlueprintCharacter.__table__.insert(),
                [
                    {
                        "project_id": project_id,
                        "name": data.get("name", ""),
                        "identity": data.get("identity"),
                        "personality": data.get("personality"),
                        "goals": data.get("goals"),
                        "abilities": data.get("abilities"),
                        "relationship_to_protagonist": data.get("relationship_to_protagonist"),
                        "power_system_id": data.get("power_system_id", None),
                        "current_power_level_id": data.get("current_power_level_id", None),
                        "extra": {k: v for k, v in data.items() if k not in {
                            "name", "identity", "personality", "goals",
                            "abilities", "relationship_to_protagonist",
                            "power_system_id", "current_power_level_id",
                        }},
                        "position": index,
                    }
                    for index, data in enumerate(blueprint.characters)
                ],
            )

        await self.session.execute(delete(BlueprintRelationship).where(BlueprintRelationship.project_id == project_id))
        if blueprint.relationships:
            await self.session.execute(
                BlueprintRelationship.__table__.insert(),
                [
                    {
                        "project_id": project_id,
                        "character_from": relation.character_from,
                        "character_to": relation.character_to,
                        "description": relation.description,
                        "position": index,
                    }
                    for index, relation in enumerate(blueprint.relationships)
                ],
            )

        await self.session.execute(delete(ChapterOutline).where(ChapterOutline.project_id == project_id))
        if blueprint.chapter_outline:
            # 按原始 chapter_number 排序后重新从 1 开始编号，确保连续且无重复
            sorted_outlines = sorted(blueprint.chapter_outline, key=lambda o: o.chapter_number)
            number_map = {o.chapter_number: i + 1 for i, o in enumerate(sorted_outlines)}
            await self.session.execute(
                ChapterOutline.__table__.insert(),
                [
                    {
                        "project_id": project_id,
                        "chapter_number": number_map[outline.chapter_number],
                        "title": outline.title,
                        "summary": outline.summary,
                        "metadata": (
                            outline.metadata
                            if getattr(outline, "metadata", None) is not None
                            else existing_outline_metadata.get(number_map[outline.chapter_number])
                        ),
                    }
                    for outline in sorted_outlines
                ],
            )
            # 同步归一化 foreshadowings 中的章节引用
            normalized_foreshadowings = []
            for fs in (blueprint.foreshadowings or []):
                new_planted = number_map.get(fs.planted_chapter, fs.planted_chapter)
                new_target = number_map.get(fs.target_chapter, fs.target_chapter) if fs.target_chapter else None
                normalized_foreshadowings.append(fs.model_copy(update={
                    "planted_chapter": new_planted,
                    "target_chapter": new_target,
                }))
            # 归一化后的 outlines 用于伏笔推断
            normalized_outlines = [
                o.model_copy(update={"chapter_number": number_map[o.chapter_number]})
                for o in sorted_outlines
            ]
        else:
            normalized_outlines = []
            normalized_foreshadowings = blueprint.foreshadowings or []

        await self._sync_blueprint_foreshadowings(
            project_id=project_id,
            outlines=normalized_outlines,
            explicit_items=normalized_foreshadowings,
            prefer_outline_inference=True,
        )

        # 同步角色/地点到实体注册表，同步势力到势力表
        await self._sync_blueprint_entities(project_id, blueprint)
        await self._sync_blueprint_factions(project_id, blueprint)

        await self.session.commit()
        await self._touch_project(project_id)

    async def patch_blueprint(self, project_id: str, patch: Dict) -> None:
        existing_outline_metadata = await self._get_outline_metadata_map(project_id)

        blueprint = await self.session.get(NovelBlueprint, project_id)
        if not blueprint:
            blueprint = NovelBlueprint(project_id=project_id)
            self.session.add(blueprint)

        if "one_sentence_summary" in patch:
            blueprint.one_sentence_summary = patch["one_sentence_summary"]
        if "full_synopsis" in patch:
            blueprint.full_synopsis = patch["full_synopsis"]
        if "world_setting" in patch and patch["world_setting"] is not None:
            # 创建新字典对象以触发 SQLAlchemy 的变更检测
            existing = blueprint.world_setting or {}
            blueprint.world_setting = {**existing, **patch["world_setting"]}
        if "characters" in patch and patch["characters"] is not None:
            await self.session.execute(delete(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id))
            for index, data in enumerate(patch["characters"]):
                self.session.add(
                    BlueprintCharacter(
                        project_id=project_id,
                        name=data.get("name", ""),
                        identity=data.get("identity"),
                        personality=data.get("personality"),
                        goals=data.get("goals"),
                        abilities=data.get("abilities"),
                        relationship_to_protagonist=data.get("relationship_to_protagonist"),
                        power_system_id=data.get("power_system_id", None),
                        current_power_level_id=data.get("current_power_level_id", None),
                        extra={k: v for k, v in data.items() if k not in {
                            "name",
                            "identity",
                            "personality",
                            "goals",
                            "abilities",
                            "relationship_to_protagonist",
                            "power_system_id",
                            "current_power_level_id"
                        }},
                        position=index,
                    )
                )
        if "relationships" in patch and patch["relationships"] is not None:
            await self.session.execute(delete(BlueprintRelationship).where(BlueprintRelationship.project_id == project_id))
            for index, relation in enumerate(patch["relationships"]):
                self.session.add(
                    BlueprintRelationship(
                        project_id=project_id,
                        character_from=relation.get("character_from"),
                        character_to=relation.get("character_to"),
                        description=relation.get("description"),
                        position=index,
                    )
                )
        if "chapter_outline" in patch and patch["chapter_outline"] is not None:
            await self.session.execute(delete(ChapterOutline).where(ChapterOutline.project_id == project_id))
            for outline in patch["chapter_outline"]:
                self.session.add(
                    ChapterOutline(
                        project_id=project_id,
                        chapter_number=outline.get("chapter_number"),
                        title=outline.get("title", ""),
                        summary=outline.get("summary"),
                        metadata=(
                            outline.get("metadata")
                            if outline.get("metadata") is not None
                            else existing_outline_metadata.get(int(outline.get("chapter_number")))
                            if outline.get("chapter_number") is not None
                            else None
                        ),
                    )
                )
        if "foreshadowings" in patch and patch["foreshadowings"] is not None:
            if "chapter_outline" in patch and patch["chapter_outline"] is not None:
                outlines_for_sync = [
                    ChapterOutlineSchema(
                        chapter_number=int(outline.get("chapter_number")),
                        title=outline.get("title", ""),
                        summary=outline.get("summary") or "",
                    )
                    for outline in patch["chapter_outline"]
                    if outline.get("chapter_number") is not None
                ]
            else:
                outlines_result = await self.session.execute(
                    select(ChapterOutline)
                    .where(ChapterOutline.project_id == project_id)
                    .order_by(ChapterOutline.chapter_number.asc())
                )
                outlines_for_sync = [
                    ChapterOutlineSchema(
                        chapter_number=outline.chapter_number,
                        title=outline.title,
                        summary=outline.summary or "",
                    )
                    for outline in outlines_result.scalars().all()
                ]

            await self._sync_blueprint_foreshadowings(
                project_id=project_id,
                outlines=outlines_for_sync,
                explicit_items=patch["foreshadowings"],
                prefer_outline_inference=False,
            )
        await self.session.commit()
        await self._touch_project(project_id)

    def _to_positive_int(self, value: Any) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = int(value)
            return number if number > 0 else None
        except (TypeError, ValueError):
            return None

    def _normalize_foreshadowing_tier(self, raw_tier: Any) -> str:
        text = str(raw_tier or "").strip().lower()
        if not text:
            return "sub"
        if any(key in text for key in ("核心", "core", "main", "主线")):
            return "core"
        if any(key in text for key in ("装饰", "decor", "decoration", "细节", "subtle", "minor")):
            return "decor"
        return "sub"

    def _tier_to_importance(self, tier: str) -> str:
        if tier == "core":
            return "major"
        if tier == "decor":
            return "subtle"
        return "minor"

    def _default_target_chapter(
        self,
        planted_chapter: int,
        tier: str,
        max_outline_chapter: int,
    ) -> Optional[int]:
        window = _FORESHADOWING_DEFAULT_WINDOWS.get(tier, _FORESHADOWING_DEFAULT_WINDOWS["sub"])
        if max_outline_chapter <= 0:
            return None
        target = planted_chapter + window
        if target > max_outline_chapter:
            target = max_outline_chapter
        return target if target > planted_chapter else None

    def _derive_foreshadowings_from_outline(
        self,
        outlines: List[ChapterOutlineSchema],
    ) -> List[Dict[str, Any]]:
        inferred: List[Dict[str, Any]] = []
        for outline in outlines:
            summary = (outline.summary or "").strip()
            if not summary:
                continue
            if not any(keyword in summary for keyword in _FORESHADOWING_HINT_KEYWORDS):
                continue

            tier = "sub"
            if any(keyword in summary for keyword in _FORESHADOWING_CORE_HINTS):
                tier = "core"
            elif any(keyword in summary for keyword in _FORESHADOWING_DECOR_HINTS):
                tier = "decor"

            inferred.append(
                {
                    "name": outline.title or f"第{outline.chapter_number}章伏笔",
                    "content": summary,
                    "chapter_number": outline.chapter_number,
                    "tier": tier,
                    "type": "hint",
                    "ai_confidence": 0.55,
                    "author_note": "由蓝图章节摘要自动提取",
                }
            )

        return inferred

    def _build_blueprint_foreshadowing_payloads(
        self,
        outlines: List[ChapterOutlineSchema],
        explicit_items: Optional[List[Any]],
        prefer_outline_inference: bool = True,
    ) -> List[Dict[str, Any]]:
        raw_payloads: List[Dict[str, Any]] = []
        explicit_list = explicit_items or []

        if explicit_list:
            for item in explicit_list:
                if isinstance(item, BlueprintForeshadowing):
                    planted_chapter = item.planted_chapter
                    target_chapter = item.target_chapter
                    raw_payloads.append(
                        {
                            "name": item.name,
                            "content": item.description,
                            "chapter_number": planted_chapter,
                            "target_reveal_chapter": target_chapter,
                            "tier": item.tier,
                            "type": item.type,
                            "reveal_method": item.reveal_method,
                            "reveal_impact": item.reveal_impact,
                            "related_characters": item.related_characters or [],
                            "related_plots": item.related_plots or [],
                            "ai_confidence": 0.9,
                        }
                    )
                    continue

                if not isinstance(item, dict):
                    continue
                raw_payloads.append(
                    {
                        "name": item.get("name") or item.get("title"),
                        "content": item.get("description") or item.get("content") or item.get("summary"),
                        "chapter_number": (
                            item.get("planted_chapter")
                            or item.get("chapter_number")
                            or item.get("chapter")
                            or item.get("start_chapter")
                        ),
                        "target_reveal_chapter": (
                            item.get("target_chapter")
                            or item.get("expected_payoff_chapter")
                            or item.get("target_reveal_chapter")
                        ),
                        "tier": item.get("tier") or item.get("level") or item.get("importance"),
                        "type": item.get("type") or item.get("foreshadowing_type") or "hint",
                        "reveal_method": item.get("reveal_method"),
                        "reveal_impact": item.get("reveal_impact"),
                        "related_characters": item.get("related_characters") or [],
                        "related_plots": item.get("related_plots") or [],
                        "ai_confidence": item.get("ai_confidence") or 0.9,
                    }
                )
        elif prefer_outline_inference:
            raw_payloads = self._derive_foreshadowings_from_outline(outlines)

        max_outline_chapter = max((outline.chapter_number for outline in outlines), default=0)
        dedup_map: Dict[tuple[int, str], Dict[str, Any]] = {}

        for payload in raw_payloads:
            planted_chapter = self._to_positive_int(payload.get("chapter_number"))
            if planted_chapter is None:
                continue
            if max_outline_chapter > 0 and planted_chapter > max_outline_chapter:
                continue

            content = str(payload.get("content") or "").strip()
            name = str(payload.get("name") or "").strip()
            if not content:
                content = name
            if not content:
                continue

            tier = self._normalize_foreshadowing_tier(payload.get("tier"))
            target_reveal_chapter = self._to_positive_int(payload.get("target_reveal_chapter"))
            if target_reveal_chapter is not None and target_reveal_chapter <= planted_chapter:
                target_reveal_chapter = None
            if target_reveal_chapter is None:
                target_reveal_chapter = self._default_target_chapter(
                    planted_chapter=planted_chapter,
                    tier=tier,
                    max_outline_chapter=max_outline_chapter,
                )

            key = (planted_chapter, (name or content)[:80].lower())
            if key in dedup_map:
                continue

            weight = _FORESHADOWING_TIER_WEIGHTS.get(tier, _FORESHADOWING_TIER_WEIGHTS["sub"])
            dedup_map[key] = {
                "name": name or content[:48],
                "content": content,
                "chapter_number": planted_chapter,
                "target_reveal_chapter": target_reveal_chapter,
                "tier": tier,
                "type": str(payload.get("type") or "hint").strip() or "hint",
                "reveal_method": payload.get("reveal_method"),
                "reveal_impact": payload.get("reveal_impact"),
                "related_characters": payload.get("related_characters") or [],
                "related_plots": payload.get("related_plots") or [],
                "importance": self._tier_to_importance(tier),
                "urgency": max(1, min(10, int(round(weight * 2)))),
                "ai_confidence": payload.get("ai_confidence"),
                "author_note": payload.get("author_note"),
            }

        return list(dedup_map.values())

    async def _sync_blueprint_foreshadowings(
        self,
        project_id: str,
        outlines: List[ChapterOutlineSchema],
        explicit_items: Optional[List[Any]],
        prefer_outline_inference: bool = True,
    ) -> None:
        await self.session.execute(
            delete(Foreshadowing).where(
                Foreshadowing.project_id == project_id,
                Foreshadowing.is_manual.is_(False),
            )
        )

        payloads = self._build_blueprint_foreshadowing_payloads(
            outlines=outlines,
            explicit_items=explicit_items,
            prefer_outline_inference=prefer_outline_inference,
        )
        if not payloads:
            return

        chapter_numbers = sorted({item["chapter_number"] for item in payloads})
        chapters_result = await self.session.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number.in_(chapter_numbers),
            )
        )
        chapter_map: Dict[int, Chapter] = {}
        for chapter in chapters_result.scalars().all():
            chapter_map.setdefault(chapter.chapter_number, chapter)

        for chapter_number in chapter_numbers:
            if chapter_number in chapter_map:
                continue
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_number,
            )
            self.session.add(chapter)
            chapter_map[chapter_number] = chapter

        await self.session.flush()

        for payload in payloads:
            chapter = chapter_map.get(payload["chapter_number"])
            if chapter is None:
                continue

            self.session.add(
                Foreshadowing(
                    project_id=project_id,
                    chapter_id=chapter.id,
                    chapter_number=payload["chapter_number"],
                    content=payload["content"],
                    type=payload["type"],
                    status="planted",
                    name=payload["name"],
                    target_reveal_chapter=payload["target_reveal_chapter"],
                    reveal_method=payload.get("reveal_method"),
                    reveal_impact=payload.get("reveal_impact"),
                    related_characters=payload.get("related_characters"),
                    related_plots=payload.get("related_plots"),
                    importance=payload["importance"],
                    urgency=payload["urgency"],
                    is_manual=False,
                    ai_confidence=payload.get("ai_confidence"),
                    author_note=payload.get("author_note"),
                )
            )

        await self.session.flush()

    # ------------------------------------------------------------------
    # 蓝图 → 实体注册表 / 势力表 同步
    # ------------------------------------------------------------------
    async def _sync_blueprint_entities(self, project_id: str, blueprint: Blueprint) -> None:
        """将蓝图角色和地点同步到 EntityRegistry（source=blueprint）。"""
        # 清理旧的 blueprint 来源实体
        await self.session.execute(
            delete(EntityRegistry).where(
                EntityRegistry.project_id == project_id,
                EntityRegistry.source == "blueprint",
            )
        )
        entities_to_add: list[EntityRegistry] = []
        # 角色 → entity_type=character
        for char_data in (blueprint.characters or []):
            name = char_data.get("name", "").strip()
            if not name:
                continue
            entities_to_add.append(EntityRegistry(
                project_id=project_id,
                entity_type="character",
                canonical_name=name,
                description=char_data.get("identity") or char_data.get("personality") or "",
                first_chapter=1,
                source="blueprint",
                confidence=1.0,
                properties={
                    k: v for k, v in char_data.items()
                    if k != "name" and v
                },
            ))
        # 地点 → entity_type=location
        world_setting = blueprint.world_setting or {}
        for location in (world_setting.get("key_locations") or []):
            loc_name = ""
            loc_desc = ""
            if isinstance(location, dict):
                loc_name = (location.get("name") or "").strip()
                loc_desc = location.get("description") or ""
            elif isinstance(location, str):
                loc_name = location.strip()
            if not loc_name:
                continue
            entities_to_add.append(EntityRegistry(
                project_id=project_id,
                entity_type="location",
                canonical_name=loc_name,
                description=loc_desc,
                source="blueprint",
                confidence=1.0,
            ))
        if entities_to_add:
            self.session.add_all(entities_to_add)
            await self.session.flush()
            logger.info("蓝图实体同步完成: project=%s entities=%d", project_id, len(entities_to_add))

    async def _sync_blueprint_factions(self, project_id: str, blueprint: Blueprint) -> None:
        """将蓝图 world_setting.factions 同步到 Faction 表。"""
        # 清理旧的势力数据
        await self.session.execute(
            delete(Faction).where(Faction.project_id == project_id)
        )
        world_setting = blueprint.world_setting or {}
        factions_data = world_setting.get("factions") or []
        if not factions_data:
            return
        factions_to_add: list[Faction] = []
        for faction_data in factions_data:
            if isinstance(faction_data, dict):
                name = (faction_data.get("name") or "").strip()
                description = faction_data.get("description") or ""
            elif isinstance(faction_data, str):
                name = faction_data.strip()
                description = ""
            else:
                continue
            if not name:
                continue
            factions_to_add.append(Faction(
                project_id=project_id,
                name=name,
                description=description,
            ))
        if factions_to_add:
            self.session.add_all(factions_to_add)
            await self.session.flush()
            logger.info("蓝图势力同步完成: project=%s factions=%d", project_id, len(factions_to_add))

    # ------------------------------------------------------------------
    # 章节与版本
    # ------------------------------------------------------------------
    async def get_outline(self, project_id: str, chapter_number: int) -> Optional[ChapterOutline]:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def _get_outline_metadata_map(self, project_id: str) -> Dict[int, dict]:
        stmt = (
            select(ChapterOutline.chapter_number, ChapterOutline.metadata_)
            .where(ChapterOutline.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        metadata_map: Dict[int, dict] = {}
        for chapter_number, metadata in result.all():
            if metadata is None:
                continue
            metadata_map[int(chapter_number)] = json.loads(json.dumps(metadata, ensure_ascii=False))
        return metadata_map

    async def update_or_create_outline(
        self,
        project_id: str,
        chapter_number: int,
        title: str,
        summary: str,
        metadata: Optional[dict] = None,
    ) -> ChapterOutline:
        """更新或创建章节大纲，支持 metadata 存储导演脚本等信息。"""
        lock = await _get_chapter_record_lock(project_id, chapter_number)
        async with lock:
            stmt = (
                select(ChapterOutline)
                .where(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == chapter_number,
                )
                .order_by(ChapterOutline.id.asc())
            )
            result = await self.session.execute(stmt)
            outlines = result.scalars().all()
            outline = outlines[0] if outlines else None
            if len(outlines) > 1 and outline is not None:
                duplicate_ids = [item.id for item in outlines[1:]]
                logger.warning(
                    "检测到重复章节大纲记录，自动收敛为首条: project=%s chapter=%s ids=%s",
                    project_id,
                    chapter_number,
                    [item.id for item in outlines],
                )
                if not outline.summary:
                    for extra in outlines[1:]:
                        if extra.summary:
                            outline.summary = extra.summary
                            break
                if metadata is None and getattr(outline, "metadata", None) is None:
                    for extra in outlines[1:]:
                        extra_metadata = getattr(extra, "metadata", None)
                        if extra_metadata is not None:
                            outline.metadata = extra_metadata
                            break
                await self.session.execute(delete(ChapterOutline).where(ChapterOutline.id.in_(duplicate_ids)))

            if outline:
                outline.title = title
                outline.summary = summary
                if metadata is not None:
                    outline.metadata = metadata
            else:
                outline = ChapterOutline(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    title=title,
                    summary=summary,
                    metadata=metadata,
                )
                self.session.add(outline)
            await self.session.flush()
            return outline

    async def _load_chapters_by_number(self, project_id: str, chapter_number: int) -> List[Chapter]:
        stmt = (
            select(Chapter)
            .options(
                selectinload(Chapter.selected_version),
                selectinload(Chapter.versions),
                selectinload(Chapter.evaluations),
            )
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
            .order_by(Chapter.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def _merge_duplicate_chapters(
        self,
        project_id: str,
        chapter_number: int,
        chapters: List[Chapter],
    ) -> Chapter:
        keeper = _select_canonical_chapter(chapters)
        duplicates = [chapter for chapter in chapters if chapter.id != keeper.id]
        if not duplicates:
            return keeper

        logger.warning(
            "检测到重复章节记录，准备自动合并: project=%s chapter=%s ids=%s keeper=%s",
            project_id,
            chapter_number,
            [chapter.id for chapter in chapters],
            keeper.id,
        )

        for candidate in sorted(chapters, key=_chapter_completeness_sort_key, reverse=True):
            if candidate.id == keeper.id:
                continue
            if not keeper.real_summary and candidate.real_summary:
                keeper.real_summary = candidate.real_summary
            if not keeper.selected_version_id and candidate.selected_version_id:
                keeper.selected_version_id = candidate.selected_version_id
            if not keeper.rag_ingest_hash and candidate.rag_ingest_hash:
                keeper.rag_ingest_hash = candidate.rag_ingest_hash
            if not _has_meaningful_chapter_status(keeper.status) and _has_meaningful_chapter_status(candidate.status):
                keeper.status = candidate.status
            if (keeper.word_count or 0) <= 0 and (candidate.word_count or 0) > 0:
                keeper.word_count = candidate.word_count

        duplicate_ids = [chapter.id for chapter in duplicates]
        await self.session.execute(
            update(ChapterVersion)
            .where(ChapterVersion.chapter_id.in_(duplicate_ids))
            .values(chapter_id=keeper.id)
        )
        await self.session.execute(
            update(ChapterEvaluation)
            .where(ChapterEvaluation.chapter_id.in_(duplicate_ids))
            .values(chapter_id=keeper.id)
        )
        await self.session.execute(
            update(Foreshadowing)
            .where(Foreshadowing.chapter_id.in_(duplicate_ids))
            .values(chapter_id=keeper.id)
        )
        await self.session.execute(
            update(Foreshadowing)
            .where(Foreshadowing.resolved_chapter_id.in_(duplicate_ids))
            .values(resolved_chapter_id=keeper.id)
        )
        await self.session.execute(
            update(ForeshadowingResolution)
            .where(ForeshadowingResolution.resolved_at_chapter_id.in_(duplicate_ids))
            .values(resolved_at_chapter_id=keeper.id)
        )
        await self.session.execute(delete(Chapter).where(Chapter.id.in_(duplicate_ids)))
        await self.session.flush()
        logger.info(
            "重复章节记录已合并: project=%s chapter=%s keeper=%s removed=%s",
            project_id,
            chapter_number,
            keeper.id,
            duplicate_ids,
        )
        return keeper

    async def get_or_create_chapter(self, project_id: str, chapter_number: int) -> Chapter:
        lock = await _get_chapter_record_lock(project_id, chapter_number)
        async with lock:
            chapters = await self._load_chapters_by_number(project_id, chapter_number)
            if chapters:
                if len(chapters) > 1:
                    await self._merge_duplicate_chapters(project_id, chapter_number, chapters)
                    chapters = await self._load_chapters_by_number(project_id, chapter_number)
                return _select_canonical_chapter(chapters)

            chapter = Chapter(project_id=project_id, chapter_number=chapter_number)
            self.session.add(chapter)
            await self.session.commit()
            await self.session.refresh(chapter)
            return chapter

    async def replace_chapter_versions(self, chapter: Chapter, contents: List[str], metadata: Optional[List[Dict]] = None) -> List[ChapterVersion]:
        await self.session.execute(delete(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id))
        versions: List[ChapterVersion] = []
        for index, content in enumerate(contents):
            extra = metadata[index] if metadata and index < len(metadata) else None
            text_content = _normalize_version_content(content, extra)
            version = ChapterVersion(
                chapter_id=chapter.id,
                content=text_content,
                metadata=extra,  # ✅ 落盘 metadata
                version_label=f"v{index+1}",
            )
            self.session.add(version)
            versions.append(version)
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)
        return versions

    async def select_chapter_version(self, chapter: Chapter, version_index: int) -> ChapterVersion:
        stmt = select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id).order_by(ChapterVersion.created_at)
        result = await self.session.execute(stmt)
        versions = result.scalars().all()
        
        if not versions or version_index < 0 or version_index >= len(versions):
            raise HTTPException(status_code=400, detail="版本索引无效")
        selected = versions[version_index]
        
        # 校验内容是否为空
        if not selected.content or len(selected.content.strip()) == 0:
            raise HTTPException(status_code=400, detail="选中的版本内容为空，无法确认为最终版")
        
        chapter.selected_version_id = selected.id
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.word_count = len(selected.content or "")
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)
        return selected

    async def add_chapter_evaluation(self, chapter: Chapter, version: Optional[ChapterVersion], feedback: str, decision: Optional[str] = None) -> None:
        evaluation = ChapterEvaluation(
            chapter_id=chapter.id,
            version_id=version.id if version else None,
            feedback=feedback,
            decision=decision,
        )
        self.session.add(evaluation)
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)

    async def delete_chapters(self, project_id: str, chapter_numbers: Iterable[int]) -> None:
        normalized_numbers = sorted(
            {
                chapter_number_int
                for chapter_number in chapter_numbers
                for chapter_number_int in [self._to_positive_int(chapter_number)]
                if chapter_number_int is not None
            }
        )
        if not normalized_numbers:
            return

        chapters_result = await self.session.execute(
            select(Chapter.id).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number.in_(normalized_numbers),
            )
        )
        chapter_ids = [chapter_id for chapter_id, in chapters_result.all()]

        # 删除被删章节中埋下的伏笔，避免伏笔管理出现悬空数据。
        await self.session.execute(
            delete(Foreshadowing).where(
                Foreshadowing.project_id == project_id,
                Foreshadowing.chapter_number.in_(normalized_numbers),
            )
        )

        # 若回收章被删，则将伏笔重新置回“未回收”状态，清空回收章引用。
        resolved_filters = [Foreshadowing.resolved_chapter_number.in_(normalized_numbers)]
        if chapter_ids:
            resolved_filters.append(Foreshadowing.resolved_chapter_id.in_(chapter_ids))
        await self.session.execute(
            update(Foreshadowing)
            .where(
                Foreshadowing.project_id == project_id,
                or_(*resolved_filters),
            )
            .values(
                resolved_chapter_id=None,
                resolved_chapter_number=None,
                status=case(
                    (
                        Foreshadowing.status.in_(_RESOLVED_FORESHADOWING_STATUSES),
                        "planted",
                    ),
                    else_=Foreshadowing.status,
                ),
            )
        )

        # 若计划回收章被删，移除目标章节，等待后续人工调整。
        await self.session.execute(
            update(Foreshadowing)
            .where(
                Foreshadowing.project_id == project_id,
                Foreshadowing.target_reveal_chapter.in_(normalized_numbers),
            )
            .values(target_reveal_chapter=None)
        )

        # 清理落在已删除章节的回收记录，避免统计口径残留。
        resolution_filters = [ForeshadowingResolution.resolved_at_chapter_number.in_(normalized_numbers)]
        if chapter_ids:
            resolution_filters.append(ForeshadowingResolution.resolved_at_chapter_id.in_(chapter_ids))
        await self.session.execute(
            delete(ForeshadowingResolution).where(or_(*resolution_filters))
        )

        await self.session.execute(
            delete(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number.in_(normalized_numbers),
            )
        )
        await self.session.execute(
            delete(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number.in_(normalized_numbers),
            )
        )
        await self._touch_project(project_id)
        self._invalidate_chapter_related_cache(project_id)
        await self._delete_chapter_vectors(project_id, normalized_numbers)

    def _invalidate_chapter_related_cache(self, project_id: str) -> None:
        try:
            cache_service = CacheService()
            cache_service.invalidate_emotion_cache(project_id)
            if not cache_service.is_available() or cache_service.redis_client is None:
                return

            cache_service.redis_client.delete(
                f"emotion_curve_enhanced:{project_id}",
                f"story_trajectory:{project_id}",
                f"creative_guidance:{project_id}",
            )
        except Exception as exc:
            logger.warning("章节删除后清理缓存失败: project=%s error=%s", project_id, exc)

    async def _delete_chapter_vectors(self, project_id: str, chapter_numbers: List[int]) -> None:
        if not chapter_numbers:
            return
        try:
            ingestion_service = ChapterIngestionService(llm_service=LLMService(self.session))
            await ingestion_service.delete_chapters(project_id, chapter_numbers)
        except Exception as exc:
            logger.warning(
                "章节删除后清理向量数据失败: project=%s chapters=%s error=%s",
                project_id,
                chapter_numbers,
                exc,
            )

    # ------------------------------------------------------------------
    # 序列化辅助
    # ------------------------------------------------------------------
    async def get_project_schema_for_admin(self, project_id: str) -> NovelProjectSchema:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return await self._serialize_project(project)

    async def get_section_data_for_admin(
        self,
        project_id: str,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return self._build_section_response(project, section)

    async def get_chapter_schema_for_admin(
        self,
        project_id: str,
        chapter_number: int,
    ) -> ChapterSchema:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return self._build_chapter_schema(project, chapter_number)

    async def _serialize_project(self, project: NovelProject) -> NovelProjectSchema:
        # 尝试从缓存获取
        cache_service = CacheService()
        cached = await cache_service.get_project_schema(project.id)
        if cached:
            try:
                return NovelProjectSchema(**cached)
            except Exception as e:
                logger.warning(f"缓存反序列化失败: {e}")

        conversations = [
            {"role": convo.role, "content": convo.content}
            for convo in sorted(project.conversations, key=lambda c: c.seq)
        ]

        foreshadowings_result = await self.session.execute(
            select(Foreshadowing)
            .where(Foreshadowing.project_id == project.id)
            .order_by(Foreshadowing.chapter_number.asc(), Foreshadowing.id.asc())
        )
        
        # 批量获取相关的力量体系和境界信息，以便在生成时使用
        from ..models.power_system import PowerSystem, PowerLevel
        power_system_ids = {c.power_system_id for c in project.characters if getattr(c, "power_system_id", None)}
        power_level_ids = {c.current_power_level_id for c in project.characters if getattr(c, "current_power_level_id", None)}
        
        power_systems_map = {}
        if power_system_ids:
            ps_result = await self.session.execute(select(PowerSystem).where(PowerSystem.id.in_(power_system_ids)))
            power_systems_map = {ps.id: ps for ps in ps_result.scalars().all()}
            
        power_levels_map = {}
        if power_level_ids:
            pl_result = await self.session.execute(select(PowerLevel).where(PowerLevel.id.in_(power_level_ids)))
            power_levels_map = {pl.id: pl for pl in pl_result.scalars().all()}
            
        # 注入力量体系名称到角色的 extra 参数中
        for character in project.characters:
            ps_id = getattr(character, "power_system_id", None)
            pl_id = getattr(character, "current_power_level_id", None)
            
            ps_text = []
            if ps_id and ps_id in power_systems_map:
                ps = power_systems_map[ps_id]
                ps_text.append(f"力量体系：{ps.name}")
                if ps.description:
                    ps_text.append(f"体系介绍：{ps.description}")
            if pl_id and pl_id in power_levels_map:
                pl = power_levels_map[pl_id]
                ps_text.append(f"当前境界/等级：{pl.name}")
                if pl.abilities:
                    ps_text.append(f"该境界能力：{pl.abilities}")
                if pl.limitations:
                    ps_text.append(f"该境界限制：{pl.limitations}")
                    
            if ps_text:
                if not character.extra:
                    character.extra = {}
                character.extra["_power_system_context"] = " | ".join(ps_text)
        
        blueprint_schema = self._build_blueprint_schema(project, list(foreshadowings_result.scalars().all()))

        outlines_map = {outline.chapter_number: outline for outline in project.outlines}
        chapters_map = _collapse_chapters_by_number(project.chapters)
        chapter_numbers = sorted(set(outlines_map.keys()) | set(chapters_map.keys()))
        chapters_schema: List[ChapterSchema] = [
            self._build_chapter_schema(
                project,
                number,
                outlines_map=outlines_map,
                chapters_map=chapters_map,
            )
            for number in chapter_numbers
        ]

        result = NovelProjectSchema(
            id=project.id,
            user_id=project.user_id,
            title=project.title,
            initial_prompt=project.initial_prompt or "",
            is_completed=bool(project.is_completed),
            conversation_history=conversations,
            blueprint=blueprint_schema,
            chapters=chapters_schema,
        )

        # 缓存结果（TTL 30 分钟）
        try:
            await cache_service.set_project_schema(project.id, result.model_dump())
        except Exception as e:
            logger.warning(f"缓存设置失败: {e}")

        return result

    async def _touch_project(self, project_id: str) -> None:
        await self.session.execute(
            update(NovelProject)
            .where(NovelProject.id == project_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()
        try:
            await CacheService().invalidate_project_schema(project_id)
        except Exception as e:
            logger.warning("项目详情缓存失效失败: project_id=%s error=%s", project_id, e)

    def _build_blueprint_schema(
        self,
        project: NovelProject,
        foreshadowings: Optional[List[Foreshadowing]] = None,
    ) -> Blueprint:
        blueprint_obj = project.blueprint
        foreshadowing_items = foreshadowings or []
        if blueprint_obj:
            return Blueprint(
                title=blueprint_obj.title or "",
                target_audience=blueprint_obj.target_audience or "",
                genre=blueprint_obj.genre or "",
                style=blueprint_obj.style or "",
                tone=blueprint_obj.tone or "",
                one_sentence_summary=blueprint_obj.one_sentence_summary or "",
                full_synopsis=blueprint_obj.full_synopsis or "",
                world_setting=blueprint_obj.world_setting or {},
                characters=[
                    {
                        "name": character.name,
                        "identity": character.identity,
                        "personality": character.personality,
                        "goals": character.goals,
                        "abilities": character.abilities,
                        "relationship_to_protagonist": character.relationship_to_protagonist,
                        "power_system_id": getattr(character, "power_system_id", None),
                        "current_power_level_id": getattr(character, "current_power_level_id", None),
                        **(character.extra or {}),
                    }
                    for character in sorted(project.characters, key=lambda c: c.position)
                ],
                relationships=[
                    {
                        "character_from": relation.character_from,
                        "character_to": relation.character_to,
                        "description": relation.description or "",
                        "relationship_type": getattr(relation, "relationship_type", None),
                    }
                    for relation in sorted(project.relationships_, key=lambda r: r.position)
                ],
                chapter_outline=[
                    ChapterOutlineSchema(
                        chapter_number=outline.chapter_number,
                        title=outline.title,
                        summary=outline.summary or "",
                        metadata=outline.metadata_,
                    )
                    for outline in sorted(project.outlines, key=lambda o: o.chapter_number)
                ],
                foreshadowings=[
                    BlueprintForeshadowing(
                        name=foreshadowing.name or "",
                        description=foreshadowing.content or "",
                        planted_chapter=foreshadowing.chapter_number,
                        target_chapter=foreshadowing.target_reveal_chapter,
                        tier=(
                            "核心"
                            if (foreshadowing.importance or "").lower() == "major"
                            else "装饰"
                            if (foreshadowing.importance or "").lower() == "subtle"
                            else "支线"
                        ),
                        type=foreshadowing.type or "hint",
                        reveal_method=foreshadowing.reveal_method,
                        reveal_impact=foreshadowing.reveal_impact,
                        related_characters=foreshadowing.related_characters or [],
                        related_plots=foreshadowing.related_plots or [],
                    )
                    for foreshadowing in foreshadowing_items
                ],
            )
        return Blueprint(
            title="",
            target_audience="",
            genre="",
            style="",
            tone="",
            one_sentence_summary="",
            full_synopsis="",
            world_setting={},
            characters=[],
            relationships=[],
            chapter_outline=[],
            foreshadowings=[],
        )

    def _build_section_response(
        self,
        project: NovelProject,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        blueprint = self._build_blueprint_schema(project)

        if section == NovelSectionType.OVERVIEW:
            data = {
                "title": project.title,
                "initial_prompt": project.initial_prompt or "",
                "status": project.status,
                "is_completed": bool(project.is_completed),
                "one_sentence_summary": blueprint.one_sentence_summary,
                "target_audience": blueprint.target_audience,
                "genre": blueprint.genre,
                "style": blueprint.style,
                "tone": blueprint.tone,
                "full_synopsis": blueprint.full_synopsis,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            }
        elif section == NovelSectionType.WORLD_SETTING:
            data = {
                "world_setting": blueprint.world_setting or {},
            }
        elif section == NovelSectionType.CHARACTERS:
            data = {
                "characters": blueprint.characters,
            }
        elif section == NovelSectionType.RELATIONSHIPS:
            data = {
                "relationships": blueprint.relationships,
            }
        elif section == NovelSectionType.CHAPTER_OUTLINE:
            data = {
                "chapter_outline": [outline.model_dump() for outline in blueprint.chapter_outline],
            }
        elif section == NovelSectionType.CHAPTERS:
            outlines_map = {outline.chapter_number: outline for outline in project.outlines}
            chapters_map = _collapse_chapters_by_number(project.chapters)
            # 只返回有大纲或有实际内容的章节，过滤掉孤立的空 Chapter 记录
            chapter_numbers = sorted(
                n for n in set(outlines_map.keys()) | set(chapters_map.keys())
                if n in outlines_map or (
                    n in chapters_map and chapters_map[n].selected_version_id is not None
                )
            )
            # 章节列表只返回元数据，不包含完整内容
            chapters = [
                self._build_chapter_schema(
                    project,
                    number,
                    outlines_map=outlines_map,
                    chapters_map=chapters_map,
                    include_content=False,
                ).model_dump()
                for number in chapter_numbers
            ]
            data = {
                "chapters": chapters,
                "total": len(chapters),
            }
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知的章节类型")

        return NovelSectionResponse(section=section, data=data)

    def _build_chapter_schema(
        self,
        project: NovelProject,
        chapter_number: int,
        *,
        outlines_map: Optional[Dict[int, ChapterOutline]] = None,
        chapters_map: Optional[Dict[int, Chapter]] = None,
        include_content: bool = True,
    ) -> ChapterSchema:
        outlines = outlines_map or {outline.chapter_number: outline for outline in project.outlines}
        chapters = chapters_map or _collapse_chapters_by_number(project.chapters)
        outline = outlines.get(chapter_number)
        chapter = chapters.get(chapter_number)

        if not outline and not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

        title = outline.title if outline else f"第{chapter_number}章"
        summary = outline.summary if outline else ""
        real_summary = chapter.real_summary if chapter else None
        content = None
        versions: Optional[List[str]] = None
        version_metadata: Optional[List[Dict[str, Any]]] = None
        recommended_version_index: Optional[int] = None
        evaluation_text: Optional[str] = None
        status_value = ChapterGenerationStatus.NOT_GENERATED.value
        word_count = 0

        if chapter:
            status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value
            word_count = chapter.word_count or 0

            if chapter.versions:
                sorted_versions = sorted(chapter.versions, key=lambda item: item.created_at)

                if include_content:
                    if chapter.selected_version:
                        content = chapter.selected_version.content
                    versions = [v.content for v in sorted_versions]

                version_metadata = []
                for idx, version in enumerate(sorted_versions):
                    meta: Dict[str, Any] = {
                        "version_id": version.id,
                        "version_label": version.version_label,
                    }
                    if isinstance(version.metadata, dict):
                        if include_content:
                            meta.update(version.metadata)
                        else:
                            ai_review_data = version.metadata.get("ai_review")
                            if ai_review_data is not None:
                                meta["ai_review"] = ai_review_data
                        ai_review = version.metadata.get("ai_review")
                        if (
                            recommended_version_index is None
                            and isinstance(ai_review, dict)
                            and ai_review.get("is_best") is True
                        ):
                            recommended_version_index = idx
                    version_metadata.append(meta)

                if recommended_version_index is None and chapter.selected_version_id:
                    for idx, version in enumerate(sorted_versions):
                        if version.id == chapter.selected_version_id:
                            recommended_version_index = idx
                            break

            if include_content and chapter.evaluations:
                latest = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
                evaluation_text = latest.feedback or latest.decision

        updated_at = None
        created_at = None
        if chapter:
            chapter_updated_at = getattr(chapter, "updated_at", None)
            chapter_created_at = getattr(chapter, "created_at", None)
            if chapter_updated_at:
                updated_at = chapter_updated_at.isoformat()
            if chapter_created_at:
                created_at = chapter_created_at.isoformat()

        return ChapterSchema(
            chapter_number=chapter_number,
            title=title,
            summary=summary,
            real_summary=real_summary,
            content=content,
            versions=versions,
            version_metadata=version_metadata,
            recommended_version_index=recommended_version_index,
            evaluation=evaluation_text,
            generation_status=ChapterGenerationStatus(status_value),
            word_count=word_count,
            updated_at=updated_at,
            created_at=created_at,
        )
