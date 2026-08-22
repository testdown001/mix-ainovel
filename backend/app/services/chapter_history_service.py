# AIMETA P=M3章节历史|R=不可变修订_恢复_文本差异|NR=不含HTTP路由_不写临时文件|E=ChapterHistoryService|X=internal|A=版本历史与恢复|D=sqlalchemy,difflib|S=db|RD=./README.ai
"""章节不可变修订历史与可视化差异（M3）。

历史记录永远不更新、不删除。恢复并不是把旧正文写回原记录，而是基于旧记录内容
创建一条 ``history_restore`` 新快照；这让后续诊断始终能够沿父版本追溯文本来源。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable

from sqlalchemy import LargeBinary, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.error_codes import DomainErrorCode, api_error
from ..core.roadmap_metrics import RoadmapMetric, emit_roadmap_metric
from ..models.novel import Chapter, ChapterVersion
from .chapter_revision_service import ChapterRevisionService, ChapterSaveResult, hash_chapter_content


SOURCE_LABELS = {
    "legacy": "历史记录",
    "generation": "整章起草",
    "manual": "手动编辑",
    "conflict_branch": "冲突分支",
    "selection_transform": "选区改写",
    "optimizer": "章节优化",
    "history_restore": "恢复历史",
}


def source_label(source: str | None) -> str:
    return SOURCE_LABELS.get(source or "legacy", "其他来源")


def _format_created_at(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _serialize(version: ChapterVersion, chapter_number: int, *, selected_id: int | None, include_content: bool) -> dict[str, Any]:
    content = version.content or ""
    data: dict[str, Any] = {
        "id": version.id,
        "chapter_number": chapter_number,
        "version_label": version.version_label,
        "source": version.source or "legacy",
        "source_label": source_label(version.source),
        "parent_version_id": version.parent_version_id,
        "content_hash": version.content_hash or hash_chapter_content(content),
        "word_count": len(content),
        "content_bytes": len(content.encode("utf-8")),
        "ai_assisted": bool(version.ai_assisted),
        "change_note": version.change_note,
        "created_at": _format_created_at(version.created_at),
        "created_by_user_id": version.created_by_user_id,
        "is_selected": version.id == selected_id,
    }
    if include_content:
        data["content"] = content
    return data


def _tokenize(text: str) -> list[str]:
    """中文按单字、英文按词分割，兼顾精确与可读的词级 Diff。"""
    return re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9_]+|\s+|[^\w\s]", text or "")


def _append_segment(target: list[dict[str, str]], kind: str, chunks: Iterable[str]) -> None:
    text = "".join(chunks)
    if not text:
        return
    if target and target[-1]["kind"] == kind:
        target[-1]["text"] += text
    else:
        target.append({"kind": kind, "text": text})


def build_text_diff(left: str, right: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """返回供左右两栏渲染的红/绿差异片段，不记录正文到日志。"""
    left_tokens, right_tokens = _tokenize(left), _tokenize(right)
    matcher = SequenceMatcher(a=left_tokens, b=right_tokens, autojunk=False)
    left_segments: list[dict[str, str]] = []
    right_segments: list[dict[str, str]] = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            _append_segment(left_segments, "equal", left_tokens[i1:i2])
            _append_segment(right_segments, "equal", right_tokens[j1:j2])
        elif opcode == "delete":
            _append_segment(left_segments, "delete", left_tokens[i1:i2])
        elif opcode == "insert":
            _append_segment(right_segments, "insert", right_tokens[j1:j2])
        else:  # replace
            _append_segment(left_segments, "delete", left_tokens[i1:i2])
            _append_segment(right_segments, "insert", right_tokens[j1:j2])
    return left_segments, right_segments


class ChapterHistoryService:
    """读取版本链与执行可追溯恢复。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _chapter(self, project_id: str, chapter_number: int) -> Chapter:
        result = await self.session.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
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

    async def _version(self, project_id: str, version_id: int) -> tuple[Chapter, ChapterVersion]:
        result = await self.session.execute(
            select(Chapter, ChapterVersion)
            .join(ChapterVersion, ChapterVersion.chapter_id == Chapter.id)
            .where(Chapter.project_id == project_id, ChapterVersion.id == version_id)
        )
        row = result.first()
        if row is None:
            raise api_error(
                404,
                DomainErrorCode.CHAPTER_VERSION_NOT_FOUND,
                "未找到指定的历史版本。",
                meta={"version_id": version_id},
            )
        return row[0], row[1]

    async def list_versions(
        self,
        project_id: str,
        chapter_number: int,
        *,
        limit: int = 30,
        before_id: int | None = None,
    ) -> dict[str, Any]:
        """按稳定 ID 游标倒序分页，并返回本章历史容量统计。"""
        chapter = await self._chapter(project_id, chapter_number)
        limit = max(1, min(int(limit), 100))
        dialect = self.session.get_bind().dialect.name
        size_expr = (
            func.length(cast(ChapterVersion.content, LargeBinary))
            if dialect == "sqlite"
            else func.octet_length(ChapterVersion.content)
        )
        total_count, total_content_bytes = (
            await self.session.execute(
                select(
                    func.count(ChapterVersion.id),
                    func.coalesce(func.sum(size_expr), 0),
                ).where(ChapterVersion.chapter_id == chapter.id)
            )
        ).one()

        query = select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
        if before_id is not None:
            query = query.where(ChapterVersion.id < before_id)
        versions = list((
            await self.session.execute(
                query.order_by(ChapterVersion.id.desc()).limit(limit + 1)
            )
        ).scalars().all())
        has_more = len(versions) > limit
        page_versions = versions[:limit]
        items = [
            _serialize(version, chapter.chapter_number, selected_id=chapter.selected_version_id, include_content=False)
            for version in page_versions
        ]
        return {
            "items": items,
            "total_count": int(total_count or 0),
            "total_content_bytes": int(total_content_bytes or 0),
            "has_more": has_more,
            "next_before_id": page_versions[-1].id if has_more and page_versions else None,
        }

    async def get_version(self, project_id: str, version_id: int) -> dict[str, Any]:
        chapter, version = await self._version(project_id, version_id)
        return _serialize(version, chapter.chapter_number, selected_id=chapter.selected_version_id, include_content=True)

    async def compare_versions(self, project_id: str, left_version_id: int, right_version_id: int) -> dict[str, Any]:
        left_chapter, left = await self._version(project_id, left_version_id)
        right_chapter, right = await self._version(project_id, right_version_id)
        if left_chapter.id != right_chapter.id:
            raise api_error(
                400,
                DomainErrorCode.INVALID_REQUEST,
                "只能比较同一章节的两个版本。",
            )
        left_segments, right_segments = build_text_diff(left.content, right.content)
        return {
            "chapter_number": left_chapter.chapter_number,
            "left_version_id": left.id,
            "right_version_id": right.id,
            "left_segments": left_segments,
            "right_segments": right_segments,
        }

    async def restore_version(
        self,
        *,
        project_id: str,
        version_id: int,
        expected_revision_id: int,
        expected_content_hash: str,
        change_note: str | None,
        actor_user_id: int | None,
    ) -> ChapterSaveResult:
        chapter, target = await self._version(project_id, version_id)
        result = await ChapterRevisionService(self.session).save(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            content=target.content,
            expected_revision_id=expected_revision_id,
            expected_content_hash=expected_content_hash,
            source="history_restore",
            parent_version_id=target.id,
            change_note=change_note or f"恢复自历史版本 #{target.id}",
            actor_user_id=actor_user_id,
        )
        emit_roadmap_metric(
            RoadmapMetric.CHAPTER_VERSION_RESTORED,
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            version_id=result.saved_version_id,
            source="history_restore",
            success=True,
        )
        return result
