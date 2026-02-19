# AIMETA P=小说服务_小说管理业务逻辑|R=小说CRUD_章节管理|NR=不含内容生成|E=NovelService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import json
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


def _normalize_version_content(raw_content: Any, metadata: Any) -> str:
    # 优先使用原始内容
    text = _coerce_text(raw_content)
    if text:
        return text
    
    # 如果没有原始内容，尝试从元数据提取（兼容旧逻辑）
    text = _coerce_text(metadata)
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
from sqlalchemy import delete, func, select, update
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
    NovelBlueprint,
    NovelConversation,
    NovelProject,
)
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

    async def get_project_schema(self, project_id: str, user_id: int) -> NovelProjectSchema:
        project = await self.ensure_project_owner(project_id, user_id)
        return await self._serialize_project(project)

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
                        "extra": {k: v for k, v in data.items() if k not in {
                            "name", "identity", "personality", "goals",
                            "abilities", "relationship_to_protagonist",
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
            await self.session.execute(
                ChapterOutline.__table__.insert(),
                [
                    {
                        "project_id": project_id,
                        "chapter_number": outline.chapter_number,
                        "title": outline.title,
                        "summary": outline.summary,
                    }
                    for outline in blueprint.chapter_outline
                ],
            )

        await self._sync_blueprint_foreshadowings(
            project_id=project_id,
            outlines=blueprint.chapter_outline,
            explicit_items=blueprint.foreshadowings,
            prefer_outline_inference=True,
        )

        await self.session.commit()
        await self._touch_project(project_id)

    async def patch_blueprint(self, project_id: str, patch: Dict) -> None:
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
                        extra={k: v for k, v in data.items() if k not in {
                            "name",
                            "identity",
                            "personality",
                            "goals",
                            "abilities",
                            "relationship_to_protagonist",
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

    async def update_or_create_outline(
        self,
        project_id: str,
        chapter_number: int,
        title: str,
        summary: str,
        metadata: Optional[dict] = None,
    ) -> ChapterOutline:
        """更新或创建章节大纲，支持 metadata 存储导演脚本等信息。"""
        stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        )
        result = await self.session.execute(stmt)
        outline = result.scalars().first()
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

    async def get_or_create_chapter(self, project_id: str, chapter_number: int) -> Chapter:
        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.selected_version))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await self.session.execute(stmt)
        chapter = result.scalars().first()
        if chapter:
            return chapter
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
        await self.session.execute(
            delete(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number.in_(list(chapter_numbers)),
            )
        )
        await self.session.execute(
            delete(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number.in_(list(chapter_numbers)),
            )
        )
        await self.session.commit()
        await self._touch_project(project_id)

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
        conversations = [
            {"role": convo.role, "content": convo.content}
            for convo in sorted(project.conversations, key=lambda c: c.seq)
        ]

        foreshadowings_result = await self.session.execute(
            select(Foreshadowing)
            .where(Foreshadowing.project_id == project.id)
            .order_by(Foreshadowing.chapter_number.asc(), Foreshadowing.id.asc())
        )
        blueprint_schema = self._build_blueprint_schema(project, list(foreshadowings_result.scalars().all()))

        outlines_map = {outline.chapter_number: outline for outline in project.outlines}
        chapters_map = {chapter.chapter_number: chapter for chapter in project.chapters}
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

        return NovelProjectSchema(
            id=project.id,
            user_id=project.user_id,
            title=project.title,
            initial_prompt=project.initial_prompt or "",
            conversation_history=conversations,
            blueprint=blueprint_schema,
            chapters=chapters_schema,
        )

    async def _touch_project(self, project_id: str) -> None:
        await self.session.execute(
            update(NovelProject)
            .where(NovelProject.id == project_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

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
            chapters_map = {chapter.chapter_number: chapter for chapter in project.chapters}
            chapter_numbers = sorted(set(outlines_map.keys()) | set(chapters_map.keys()))
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
        chapters = chapters_map or {chapter.chapter_number: chapter for chapter in project.chapters}
        outline = outlines.get(chapter_number)
        chapter = chapters.get(chapter_number)

        if not outline and not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

        title = outline.title if outline else f"第{chapter_number}章"
        summary = outline.summary if outline else ""
        real_summary = chapter.real_summary if chapter else None
        content = None
        versions: Optional[List[str]] = None
        evaluation_text: Optional[str] = None
        status_value = ChapterGenerationStatus.NOT_GENERATED.value
        word_count = 0

        if chapter:
            status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value
            word_count = chapter.word_count or 0

            # 只有在 include_content=True 时才包含完整内容
            if include_content:
                if chapter.selected_version:
                    content = chapter.selected_version.content
                if chapter.versions:
                    versions = [
                        v.content
                        for v in sorted(chapter.versions, key=lambda item: item.created_at)
                    ]
                if chapter.evaluations:
                    latest = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
                    evaluation_text = latest.feedback or latest.decision

        return ChapterSchema(
            chapter_number=chapter_number,
            title=title,
            summary=summary,
            real_summary=real_summary,
            content=content,
            versions=versions,
            evaluation=evaluation_text,
            generation_status=ChapterGenerationStatus(status_value),
            word_count=word_count,
        )
