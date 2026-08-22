# AIMETA P=M2章节可靠保存|R=乐观锁_版本快照_冲突保护|NR=不含HTTP路由_不含AI处理|E=ChapterRevisionService|X=internal|A=章节正文条件写入|D=sqlalchemy|S=db|RD=./README.ai
"""章节正文的可靠保存边界（M2）。

`ChapterVersion.content` 是历史文本，手工编辑不可原地覆写。此服务以章节级
`revision_id` 和 `content_hash` 实现条件写入；冲突时只抛出无正文的结构化错误，
客户端必须再读取当前版本以展示冲突处理 UI。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.error_codes import DomainErrorCode, api_error
from ..core.roadmap_metrics import RoadmapMetric, emit_roadmap_metric
from ..models.novel import Chapter, ChapterVersion


ChapterVersionSource = Literal[
    "legacy",
    "generation",
    "manual",
    "conflict_branch",
    "selection_transform",
    "optimizer",
    "history_restore",
]


def hash_chapter_content(content: str | None) -> str:
    """返回 UTF-8 正文的稳定 SHA-256，不记录或暴露正文。"""
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChapterRevision:
    chapter_number: int
    revision_id: int
    content_hash: str
    selected_version_id: Optional[int]
    content: str


@dataclass(frozen=True)
class ChapterSaveResult:
    status: Literal["saved", "branched"]
    revision: ChapterRevision
    saved_version_id: int


class ChapterRevisionService:
    """协调编辑器保存，保证同一基线只能成功写入一次。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _load_chapter(self, project_id: str, chapter_number: int) -> Chapter:
        result = await self.session.execute(
            select(Chapter)
            # 同一请求会话在条件 UPDATE 后可能仍持有旧的 selected_version 关系；强制
            # 刷新，既保证网络重试的幂等判断正确，也避免给调用方陈旧哈希。
            .execution_options(populate_existing=True)
            .options(selectinload(Chapter.selected_version))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
            .order_by(Chapter.id.asc())
        )
        chapter = result.scalars().first()
        if chapter is None:
            raise api_error(
                404,
                DomainErrorCode.CHAPTER_NOT_FOUND,
                "未找到指定章节。",
                meta={"chapter_number": chapter_number},
            )
        return chapter

    @staticmethod
    def _snapshot(chapter: Chapter) -> ChapterRevision:
        content = chapter.selected_version.content if chapter.selected_version else ""
        # 旧数据在迁移后没有 hash 时，以真实文本即时计算；绝不信任陈旧缓存值。
        content_hash = hash_chapter_content(content)
        return ChapterRevision(
            chapter_number=chapter.chapter_number,
            revision_id=int(chapter.revision_id or 0),
            content_hash=content_hash,
            selected_version_id=chapter.selected_version_id,
            content=content,
        )

    async def get_revision(self, project_id: str, chapter_number: int) -> ChapterRevision:
        chapter = await self._load_chapter(project_id, chapter_number)
        return self._snapshot(chapter)

    @staticmethod
    def _conflict_error(snapshot: ChapterRevision):
        return api_error(
            409,
            DomainErrorCode.VERSION_CONFLICT,
            "章节已在其他位置更新，请先处理冲突。",
            meta={
                "chapter_number": snapshot.chapter_number,
                "server_revision_id": snapshot.revision_id,
                "server_content_hash": snapshot.content_hash,
                "selected_version_id": snapshot.selected_version_id,
            },
        )

    async def save(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
        expected_revision_id: int,
        expected_content_hash: str,
        mode: Literal["save", "branch"] = "save",
        source: ChapterVersionSource = "manual",
        parent_version_id: Optional[int] = None,
        change_note: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> ChapterSaveResult:
        """写入一个新版本，或在冲突时保存为非选中分支。

        正常保存使用 SQL 条件 UPDATE，使两个请求即使同时通过读取阶段，也只能有一个
        改变当前版本。网络超时后的同内容重试被识别为幂等成功。
        """
        chapter = await self._load_chapter(project_id, chapter_number)
        current = self._snapshot(chapter)
        new_hash = hash_chapter_content(content)

        if mode == "branch":
            branch = ChapterVersion(
                chapter_id=chapter.id,
                content=content,
                version_label=f"manual_branch_r{current.revision_id}",
                ai_assisted=False,
                parent_version_id=current.selected_version_id,
                source="conflict_branch",
                content_hash=new_hash,
                change_note="并发冲突时保留的本地分支",
                created_by_user_id=actor_user_id,
                metadata={
                    "m2_edit": {
                        "kind": "conflict_branch",
                        "parent_version_id": current.selected_version_id,
                        "base_revision_id": expected_revision_id,
                        "base_content_hash": expected_content_hash,
                    }
                },
            )
            self.session.add(branch)
            await self.session.flush()
            await self.session.commit()
            emit_roadmap_metric(
                RoadmapMetric.CHAPTER_SAVE_SUCCEEDED,
                project_id=project_id,
                chapter_number=chapter_number,
                mode="branch",
            )
            return ChapterSaveResult("branched", current, branch.id)

        is_expected = (
            expected_revision_id == current.revision_id
            and expected_content_hash == current.content_hash
        )
        if not is_expected:
            # 请求在服务端已落库、但响应在网络途中丢失时，允许安全重试；其他情况必须
            # 明确进入冲突 UI，绝不让后发请求覆盖先发请求。
            if (
                current.revision_id == expected_revision_id + 1
                and current.content_hash == new_hash
                and current.selected_version_id is not None
            ):
                return ChapterSaveResult("saved", current, current.selected_version_id)
            emit_roadmap_metric(
                RoadmapMetric.CHAPTER_SAVE_CONFLICT,
                project_id=project_id,
                chapter_number=chapter_number,
            )
            raise self._conflict_error(current)

        version = ChapterVersion(
            chapter_id=chapter.id,
            content=content,
            version_label=f"{source}_r{current.revision_id + 1}",
            ai_assisted=source in {"selection_transform", "optimizer"},
            parent_version_id=(
                parent_version_id if parent_version_id is not None else current.selected_version_id
            ),
            source=source,
            content_hash=new_hash,
            change_note=(change_note or None),
            created_by_user_id=actor_user_id,
            metadata={
                "m2_edit": {
                    "kind": source,
                    "parent_version_id": (
                        parent_version_id if parent_version_id is not None else current.selected_version_id
                    ),
                    "base_revision_id": current.revision_id,
                    "base_content_hash": current.content_hash,
                }
            },
        )
        self.session.add(version)
        await self.session.flush()

        updated = await self.session.execute(
            update(Chapter)
            .where(
                Chapter.id == chapter.id,
                Chapter.revision_id == expected_revision_id,
            )
            .values(
                selected_version_id=version.id,
                revision_id=expected_revision_id + 1,
                content_hash=new_hash,
                status="successful",
                word_count=len(content),
                updated_at=func.now(),
            )
        )
        if updated.rowcount != 1:
            # 已 flush 的候选版本必须随同回滚，不能遗留成一条看似有效的分支。
            await self.session.rollback()
            latest = await self.get_revision(project_id, chapter_number)
            emit_roadmap_metric(
                RoadmapMetric.CHAPTER_SAVE_CONFLICT,
                project_id=project_id,
                chapter_number=chapter_number,
            )
            raise self._conflict_error(latest)

        await self.session.commit()
        revision = ChapterRevision(
            chapter_number=chapter_number,
            revision_id=expected_revision_id + 1,
            content_hash=new_hash,
            selected_version_id=version.id,
            content=content,
        )
        emit_roadmap_metric(
            RoadmapMetric.CHAPTER_SAVE_SUCCEEDED,
            project_id=project_id,
            chapter_number=chapter_number,
            mode=source,
        )
        return ChapterSaveResult("saved", revision, version.id)
