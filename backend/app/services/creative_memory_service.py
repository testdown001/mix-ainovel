# AIMETA P=创作记忆服务_候选学习与分级注入|R=四级作用域_人工确认_生成回执|NR=不替代章节版本历史|E=CreativeMemoryService|X=internal|A=偏好学习与检索|D=sqlalchemy,pydantic,llm_service|S=db,llm
from __future__ import annotations

import difflib
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.creative_memory import (
    CreativeMemoryItem,
    CreativeMemoryLearningEvent,
    CreativeMemoryReceipt,
)
from ..models.novel import ChapterVersion, Volume
from ..schemas.creative_memory import CreativeMemoryCreate, CreativeMemoryUpdate
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class _CandidateDraft(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    content: str = Field(min_length=4, max_length=500)
    category: Literal[
        "style", "viewpoint", "rhetoric", "dialogue", "pacing", "structure", "taboo"
    ] = "style"
    scope: Literal["author", "novel", "volume", "chapter"] = "novel"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=500)
    evidence_summary: str = Field(default="", max_length=300)


class _CandidateBatch(BaseModel):
    candidates: List[_CandidateDraft] = Field(default_factory=list, max_length=3)


class CreativeMemoryService:
    """把有证据的作者选择转成候选规则，确认后才允许进入提示词。"""

    MAX_ACTIVE_ITEMS = 12
    MAX_PROMPT_CHARS = 3000

    def __init__(self, session: AsyncSession, llm_service: Optional[LLMService] = None):
        self.session = session
        self.llm_service = llm_service

    async def list_items(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: Optional[int] = None,
        status: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> List[CreativeMemoryItem]:
        conditions = [CreativeMemoryItem.user_id == user_id]
        if status:
            conditions.append(CreativeMemoryItem.status == status)
        if scope:
            conditions.append(CreativeMemoryItem.scope == scope)

        # 作者级已确认规则跨作品可见；候选只在产生它的作品中展示，防止泄漏到别的书。
        conditions.append(
            or_(
                and_(
                    CreativeMemoryItem.scope == "author",
                    CreativeMemoryItem.status == "active",
                ),
                CreativeMemoryItem.source_project_id == project_id,
                CreativeMemoryItem.project_id == project_id,
            )
        )
        if chapter_number is not None:
            volume_number = await self._resolve_volume_number(project_id, chapter_number)
            conditions.append(
                or_(
                    CreativeMemoryItem.scope.in_(["author", "novel"]),
                    and_(
                        CreativeMemoryItem.scope == "volume",
                        CreativeMemoryItem.volume_number == volume_number,
                    ),
                    and_(
                        CreativeMemoryItem.scope == "chapter",
                        CreativeMemoryItem.chapter_number == chapter_number,
                    ),
                    # 候选仍需显示，作者可把建议改成其他作用域后确认。
                    CreativeMemoryItem.status == "candidate",
                )
            )
        result = await self.session.execute(
            select(CreativeMemoryItem)
            .where(*conditions)
            .order_by(
                CreativeMemoryItem.pinned.desc(),
                CreativeMemoryItem.status.asc(),
                CreativeMemoryItem.confidence.desc(),
                CreativeMemoryItem.updated_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def latest_receipt(
        self, *, user_id: int, project_id: str, chapter_number: int
    ) -> Optional[CreativeMemoryReceipt]:
        result = await self.session.execute(
            select(CreativeMemoryReceipt)
            .where(
                CreativeMemoryReceipt.user_id == user_id,
                CreativeMemoryReceipt.project_id == project_id,
                CreativeMemoryReceipt.chapter_number == chapter_number,
            )
            .order_by(CreativeMemoryReceipt.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def create_manual(
        self,
        *,
        user_id: int,
        project_id: str,
        payload: CreativeMemoryCreate,
    ) -> CreativeMemoryItem:
        item = CreativeMemoryItem(
            user_id=user_id,
            project_id=None if payload.scope == "author" else project_id,
            source_project_id=project_id,
            scope=payload.scope,
            volume_number=payload.volume_number if payload.scope == "volume" else None,
            chapter_number=payload.chapter_number if payload.scope == "chapter" else None,
            category=payload.category,
            title=payload.title.strip(),
            content=payload.content.strip(),
            status="active",
            confidence=1.0,
            pinned=payload.pinned,
            source_type="manual",
            evidence={"kind": "manual"},
            dedupe_key=self._dedupe_key(
                user_id, project_id, payload.scope, payload.category, payload.content
            ),
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_item(
        self,
        *,
        item: CreativeMemoryItem,
        project_id: str,
        payload: CreativeMemoryUpdate,
    ) -> CreativeMemoryItem:
        data = payload.model_dump(exclude_unset=True)
        for key in ("title", "content", "category", "pinned"):
            if key in data:
                setattr(item, key, data[key])

        next_scope = data.get("scope", item.scope)
        next_volume = data.get("volume_number", item.volume_number)
        next_chapter = data.get("chapter_number", item.chapter_number)
        if next_scope == "volume" and not next_volume:
            raise ValueError("卷级记忆必须指定卷号")
        if next_scope == "chapter" and not next_chapter:
            raise ValueError("章节级记忆必须指定章节号")
        item.scope = next_scope
        item.project_id = None if next_scope == "author" else project_id
        item.volume_number = next_volume if next_scope == "volume" else None
        item.chapter_number = next_chapter if next_scope == "chapter" else None
        if "status" in data:
            item.status = data["status"]
        item.dedupe_key = self._dedupe_key(
            item.user_id,
            project_id,
            item.scope,
            item.category,
            item.content,
        )
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def archive_item(self, item: CreativeMemoryItem) -> None:
        item.status = "archived"
        await self.session.commit()

    async def get_owned_item(
        self, *, memory_id: int, user_id: int, project_id: str
    ) -> Optional[CreativeMemoryItem]:
        result = await self.session.execute(
            select(CreativeMemoryItem).where(
                CreativeMemoryItem.id == memory_id,
                CreativeMemoryItem.user_id == user_id,
                or_(
                    CreativeMemoryItem.project_id == project_id,
                    CreativeMemoryItem.source_project_id == project_id,
                    and_(
                        CreativeMemoryItem.scope == "author",
                        CreativeMemoryItem.project_id.is_(None),
                    ),
                ),
            )
        )
        return result.scalars().first()

    async def active_for_generation(
        self, *, user_id: int, project_id: str, chapter_number: int
    ) -> List[CreativeMemoryItem]:
        volume_number = await self._resolve_volume_number(project_id, chapter_number)
        scope_condition = or_(
            and_(
                CreativeMemoryItem.scope == "author",
                CreativeMemoryItem.project_id.is_(None),
            ),
            and_(
                CreativeMemoryItem.scope == "novel",
                CreativeMemoryItem.project_id == project_id,
            ),
            and_(
                CreativeMemoryItem.scope == "volume",
                CreativeMemoryItem.project_id == project_id,
                CreativeMemoryItem.volume_number == volume_number,
            ),
            and_(
                CreativeMemoryItem.scope == "chapter",
                CreativeMemoryItem.project_id == project_id,
                CreativeMemoryItem.chapter_number == chapter_number,
            ),
        )
        result = await self.session.execute(
            select(CreativeMemoryItem)
            .where(
                CreativeMemoryItem.user_id == user_id,
                CreativeMemoryItem.status == "active",
                scope_condition,
            )
            .order_by(
                CreativeMemoryItem.pinned.desc(),
                CreativeMemoryItem.confidence.desc(),
                CreativeMemoryItem.updated_at.desc(),
            )
            .limit(self.MAX_ACTIVE_ITEMS)
        )
        return list(result.scalars().all())

    async def build_generation_context(
        self, *, user_id: int, project_id: str, chapter_number: int
    ) -> Dict[str, Any]:
        items = await self.active_for_generation(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
        )
        serialized = [self._serialize_receipt_item(item) for item in items]
        prompt = self._format_prompt(items)
        receipt = CreativeMemoryReceipt(
            id=str(uuid.uuid4()),
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            memory_ids=[item.id for item in items],
            items=serialized,
        )
        self.session.add(receipt)
        now = datetime.now(timezone.utc)
        for item in items:
            item.use_count = (item.use_count or 0) + 1
            item.last_used_at = now
        await self.session.commit()
        return {
            "prompt": prompt,
            "receipt_id": receipt.id,
            "memory_ids": receipt.memory_ids,
            "items": serialized,
        }

    @classmethod
    async def prefetch_generation_context(
        cls, *, user_id: int, project_id: str, chapter_number: int
    ) -> Dict[str, Any]:
        from ..db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            return await cls(session).build_generation_context(
                user_id=user_id,
                project_id=project_id,
                chapter_number=chapter_number,
            )

    async def learn_revision(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        version_id: int,
    ) -> List[CreativeMemoryItem]:
        result = await self.session.execute(
            select(ChapterVersion)
            .where(ChapterVersion.id == version_id)
            .options(selectinload(ChapterVersion.parent_version))
        )
        version = result.scalars().first()
        parent = version.parent_version if version else None
        if not version or not parent:
            return []
        if not (parent.ai_assisted or parent.source in {"generation", "optimizer", "selection_transform"}):
            return []
        diff = self._diff_excerpt(parent.content or "", version.content or "")
        if len(diff.replace(" ", "")) < 80:
            return []
        return await self._learn_candidates(
            event_key=f"revision:{version_id}",
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            source_type="revision",
            source_version_id=version_id,
            prompt=(
                "下面是作者在 AI 草稿上做出的真实改动。只总结可复用的写作偏好，"
                "不要学习本章专有剧情、姓名、地点或事实；无法确定时返回空数组。\n\n"
                f"修改差异：\n{diff}"
            ),
            evidence={"kind": "revision", "diff_excerpt": diff[:2000]},
        )

    async def learn_selection(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        selected_version_id: int,
    ) -> List[CreativeMemoryItem]:
        version = await self.session.get(ChapterVersion, selected_version_id)
        if not version:
            return []
        result = await self.session.execute(
            select(ChapterVersion)
            .where(
                ChapterVersion.chapter_id == version.chapter_id,
                ChapterVersion.id != selected_version_id,
            )
            .order_by(ChapterVersion.created_at.desc())
            .limit(2)
        )
        alternatives = list(result.scalars().all())
        if not alternatives:
            return []
        comparison = "\n\n".join(
            f"未选版本{idx}：\n{self._excerpt(item.content)}"
            for idx, item in enumerate(alternatives, 1)
        )
        return await self._learn_candidates(
            event_key=f"selection:{selected_version_id}",
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            source_type="version_selection",
            source_version_id=selected_version_id,
            prompt=(
                "作者从多个 AI 版本中选中了一个。比较文本，只归纳可复用的叙事视角、"
                "句法、对话、节奏或修辞取舍；不得把剧情差异当成永久偏好。无法可靠判断则返回空数组。\n\n"
                f"选中版本：\n{self._excerpt(version.content)}\n\n{comparison}"
            ),
            evidence={
                "kind": "version_selection",
                "selected_excerpt": self._excerpt(version.content, 900),
                "alternative_count": len(alternatives),
            },
        )

    async def learn_transform(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        version_id: int,
        instruction: str,
        original_text: str,
        transformed_text: str,
    ) -> List[CreativeMemoryItem]:
        return await self._learn_candidates(
            event_key=f"transform:{version_id}",
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            source_type="selection_transform",
            source_version_id=version_id,
            prompt=(
                "作者明确采纳了一次局部 AI 改写。根据作者指令和前后文本，只提取可复用"
                "的写作偏好；一次性剧情要求应返回空数组。\n\n"
                f"作者指令：{instruction or '未填写'}\n"
                f"改写前：{self._excerpt(original_text, 700)}\n"
                f"采纳后：{self._excerpt(transformed_text, 700)}"
            ),
            evidence={
                "kind": "selection_transform",
                "instruction": (instruction or "")[:300],
                "before": self._excerpt(original_text, 500),
                "after": self._excerpt(transformed_text, 500),
            },
        )

    async def _learn_candidates(
        self,
        *,
        event_key: str,
        user_id: int,
        project_id: str,
        chapter_number: int,
        source_type: str,
        source_version_id: Optional[int],
        prompt: str,
        evidence: Dict[str, Any],
    ) -> List[CreativeMemoryItem]:
        if self.llm_service is None:
            return []
        existing = await self.session.execute(
            select(CreativeMemoryLearningEvent).where(
                CreativeMemoryLearningEvent.event_key == event_key
            )
        )
        if existing.scalars().first():
            return []
        event = CreativeMemoryLearningEvent(
            id=str(uuid.uuid4()),
            event_key=event_key,
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            source_type=source_type,
            source_version_id=source_version_id,
            status="processing",
            candidate_ids=[],
        )
        self.session.add(event)
        await self.session.commit()
        try:
            batch = await self.llm_service.generate_structured(
                prompt=prompt,
                schema=_CandidateBatch,
                system_prompt=(
                    "你负责识别作者长期写作偏好，而不是提取故事事实。每条 content 必须写成"
                    "可直接执行的中文规则。scope 含义：author=跨作品稳定习惯，novel=仅本书，"
                    "volume=仅当前卷，chapter=仅当前章。证据不足就不要输出。"
                ),
                temperature=0.1,
                user_id=user_id,
                max_tokens=1200,
                default=_CandidateBatch(),
            )
            volume_number = await self._resolve_volume_number(project_id, chapter_number)
            created: List[CreativeMemoryItem] = []
            for draft in batch.candidates[:3]:
                draft_scope = draft.scope
                if draft_scope == "volume" and volume_number is None:
                    draft_scope = "novel"
                key = self._dedupe_key(
                    user_id, project_id, draft_scope, draft.category, draft.content
                )
                duplicate = await self.session.execute(
                    select(CreativeMemoryItem.id).where(CreativeMemoryItem.dedupe_key == key)
                )
                if duplicate.scalar_one_or_none() is not None:
                    continue
                item = CreativeMemoryItem(
                    user_id=user_id,
                    project_id=None if draft_scope == "author" else project_id,
                    source_project_id=project_id,
                    scope=draft_scope,
                    volume_number=volume_number if draft_scope == "volume" else None,
                    chapter_number=chapter_number if draft_scope == "chapter" else None,
                    category=draft.category,
                    title=draft.title.strip(),
                    content=draft.content.strip(),
                    rationale=(draft.rationale or "").strip() or None,
                    status="candidate",
                    confidence=draft.confidence,
                    source_type=source_type,
                    source_version_id=source_version_id,
                    evidence={**evidence, "summary": draft.evidence_summary},
                    dedupe_key=key,
                )
                self.session.add(item)
                created.append(item)
            await self.session.flush()
            event.candidate_ids = [item.id for item in created]
            event.status = "completed"
            event.completed_at = datetime.now(timezone.utc)
            await self.session.commit()
            return created
        except Exception as exc:
            logger.warning("创作记忆候选学习失败（不影响保存/选版）: %s", exc)
            await self.session.rollback()
            persisted = await self.session.get(CreativeMemoryLearningEvent, event.id)
            if persisted:
                persisted.status = "failed"
                persisted.error_message = str(exc)[:1000]
                persisted.completed_at = datetime.now(timezone.utc)
                await self.session.commit()
            return []

    async def _resolve_volume_number(
        self, project_id: str, chapter_number: int
    ) -> Optional[int]:
        result = await self.session.execute(
            select(Volume.position)
            .where(
                Volume.project_id == project_id,
                Volume.start_chapter <= chapter_number,
                Volume.end_chapter >= chapter_number,
            )
            .order_by(Volume.position.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    def _format_prompt(cls, items: Iterable[CreativeMemoryItem]) -> str:
        labels = {"author": "作者", "novel": "本书", "volume": "本卷", "chapter": "本章"}
        lines: List[str] = []
        used = 0
        for item in items:
            line = f"- [{labels.get(item.scope, item.scope)}·{item.title}] {item.content.strip()}"
            if used + len(line) > cls.MAX_PROMPT_CHARS:
                break
            lines.append(line)
            used += len(line)
        return "\n".join(lines)

    @staticmethod
    def _serialize_receipt_item(item: CreativeMemoryItem) -> Dict[str, Any]:
        return {
            "id": item.id,
            "scope": item.scope,
            "category": item.category,
            "title": item.title,
            "content": item.content,
        }

    @staticmethod
    def _dedupe_key(
        user_id: int, project_id: str, scope: str, category: str, content: str
    ) -> str:
        normalized = "".join((content or "").lower().split())
        scope_project = "author" if scope == "author" else project_id
        raw = f"{user_id}|{scope_project}|{scope}|{category}|{normalized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _excerpt(text: str, limit: int = 1200) -> str:
        value = (text or "").strip()
        if len(value) <= limit:
            return value
        half = max(1, limit // 2)
        return f"{value[:half]}\n……\n{value[-half:]}"

    @staticmethod
    def _diff_excerpt(before: str, after: str, limit: int = 2600) -> str:
        diff = "\n".join(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile="AI草稿",
                tofile="作者定稿",
                lineterm="",
                n=2,
            )
        )
        return CreativeMemoryService._excerpt(diff, limit)


async def review_creative_memory_revision(
    *, user_id: int, project_id: str, chapter_number: int, version_id: int
) -> None:
    from ..db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await CreativeMemoryService(session, LLMService(session)).learn_revision(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            version_id=version_id,
        )


async def review_creative_memory_selection(
    *, user_id: int, project_id: str, chapter_number: int, selected_version_id: int
) -> None:
    from ..db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await CreativeMemoryService(session, LLMService(session)).learn_selection(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            selected_version_id=selected_version_id,
        )


async def review_creative_memory_transform(
    *,
    user_id: int,
    project_id: str,
    chapter_number: int,
    version_id: int,
    instruction: str,
    original_text: str,
    transformed_text: str,
) -> None:
    from ..db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await CreativeMemoryService(session, LLMService(session)).learn_transform(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            version_id=version_id,
            instruction=instruction,
            original_text=original_text,
            transformed_text=transformed_text,
        )
