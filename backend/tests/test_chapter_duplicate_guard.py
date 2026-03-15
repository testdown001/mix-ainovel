import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.chapter_post_processor import ChapterPostProcessor
from app.services.novel_service import _collapse_chapters_by_number


class _ScalarListResult:
    def __init__(self, values):
        self._values = list(values)

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


def test_collapse_chapters_by_number_prefers_contentful_duplicate():
    chapter_empty = SimpleNamespace(
        id=249,
        chapter_number=34,
        selected_version_id=None,
        real_summary=None,
        versions=[],
        evaluations=[],
        word_count=0,
        status="not_generated",
    )
    chapter_rich = SimpleNamespace(
        id=248,
        chapter_number=34,
        selected_version_id=525,
        real_summary="已有摘要",
        versions=[SimpleNamespace(id=525)],
        evaluations=[],
        word_count=3980,
        status="successful",
    )

    chapters_map = _collapse_chapters_by_number([chapter_empty, chapter_rich])

    assert chapters_map[34] is chapter_rich


def test_chapter_post_processor_writes_summary_to_canonical_duplicate():
    chapter_empty = SimpleNamespace(
        id=249,
        selected_version_id=None,
        real_summary=None,
        word_count=0,
        status="not_generated",
    )
    chapter_rich = SimpleNamespace(
        id=248,
        selected_version_id=525,
        real_summary=None,
        word_count=3980,
        status="successful",
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=_ScalarListResult([chapter_empty, chapter_rich])),
        commit=AsyncMock(),
    )
    llm_service = SimpleNamespace(get_summary=AsyncMock(return_value="<think>draft</think>新摘要"))
    processor = ChapterPostProcessor(session, llm_service)

    summary = asyncio.run(
        processor._ensure_summary(
            "project-1",
            34,
            "章节正文",
            7,
            force=False,
        )
    )

    assert summary == "新摘要"
    assert chapter_rich.real_summary == "新摘要"
    assert chapter_empty.real_summary is None
    session.commit.assert_awaited_once()
