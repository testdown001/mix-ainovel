import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _ensure_models_loaded():
    """确保所有 ORM 模型在测试前加载完毕。"""
    import app.models  # noqa: F401
    import app.models.user_quota  # noqa: F401


def _get_service_class():
    mod = importlib.import_module("app.services.book_summary_service")
    return mod.BookSummaryService


class _DummyResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return self

    def first(self):
        return self._scalar

    def all(self):
        return self._rows


class _DummySession:
    """使用 AsyncMock + side_effect 链式返回不同结果。"""

    def __init__(self, *, execute_results=None):
        self._results = list(execute_results or [])
        self._call_idx = 0
        self._added = []
        self._committed = False
        self.execute = AsyncMock(side_effect=self._execute_side_effect)

    async def _execute_side_effect(self, *args, **kwargs):
        if self._call_idx < len(self._results):
            result = self._results[self._call_idx]
            self._call_idx += 1
            return result
        return _DummyResult()

    def add(self, obj):
        self._added.append(obj)

    async def commit(self):
        self._committed = True


def _mock_llm(summary_text="全书摘要内容"):
    llm = SimpleNamespace()
    llm.get_summary = AsyncMock(return_value=summary_text)
    llm.get_embedding = AsyncMock(return_value=[0.1] * 10)
    return llm


def _make_volume_summary(volume_number, title, summary, chapter_start, chapter_end):
    """创建模拟的 VolumeSummary 对象。"""
    return SimpleNamespace(
        volume_number=volume_number,
        title=title,
        summary=summary,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
        chapter_count=chapter_end - chapter_start + 1,
        source_hash="abc123",
        updated_at=None,
    )


def test_compute_source_hash_stable():
    """hash 稳定且内容变化时 hash 变化。"""
    cls = _get_service_class()

    vols_a = [
        {"volume_number": 1, "summary": "卷1摘要"},
        {"volume_number": 2, "summary": "卷2摘要"},
    ]
    vols_b = [
        {"volume_number": 1, "summary": "卷1摘要"},
        {"volume_number": 2, "summary": "卷2变了"},
    ]

    hash_a1 = cls._compute_source_hash(vols_a)
    hash_a2 = cls._compute_source_hash(vols_a)
    hash_b = cls._compute_source_hash(vols_b)

    assert hash_a1 == hash_a2
    assert hash_a1 != hash_b


def _source_aware_service(monkeypatch, *, summary="生成的全书摘要"):
    import hashlib
    from app.services.retrieval_scope import RetrievalScope
    source = dict(project_id="proj-1", chapter_number=1, source_version_id=1,
                  source_content_hash="hash", adoption_revision_id=1, narrative_base="base")
    volume = _make_volume_summary(1, "第1卷", "卷1摘要", 1, 1)
    monkeypatch.setattr("app.services.volume_summary_service.VolumeSummaryService.get_all_volume_summaries",
                        AsyncMock(return_value=[volume]))
    monkeypatch.setattr("app.services.retrieval_scope.build_retrieval_scope", AsyncMock(
                        return_value=RetrievalScope("proj-1", 2, {1: source})))
    memory = SimpleNamespace(book_summary=None, extra={"volume_summary_sources": {
        "1": {"summary_hash": hashlib.sha256(volume.summary.encode()).hexdigest(),
              "contributing_sources": [source]}}})
    session = _DummySession()
    service = _get_service_class()(session, _mock_llm(summary))
    service._get_memory = AsyncMock(return_value=memory)
    service._get_or_create_memory = AsyncMock(return_value=memory)
    service._ingest_book_summary = AsyncMock()
    return service, memory, volume


def test_update_book_summary_generates_summary(monkeypatch):
    service, memory, _ = _source_aware_service(monkeypatch)
    result = asyncio.run(service.update_book_summary("proj-1", user_id=1))
    assert result == "生成的全书摘要"
    assert service.session._committed
    service.llm_service.get_summary.assert_called_once()
    assert memory.extra["book_summary_sources"]["contributing_sources"]


def test_update_book_summary_skips_when_no_volumes(monkeypatch):
    monkeypatch.setattr("app.services.volume_summary_service.VolumeSummaryService.get_all_volume_summaries",
                        AsyncMock(return_value=[]))
    service = _get_service_class()(_DummySession(), _mock_llm())
    assert asyncio.run(service.update_book_summary("proj-1", user_id=1)) is None
    service.llm_service.get_summary.assert_not_called()


def test_update_book_summary_skips_unchanged(monkeypatch):
    service, memory, volume = _source_aware_service(monkeypatch)
    memory.book_summary = "旧的全书摘要"
    memory.extra["book_summary_hash"] = service._compute_source_hash([{
        "volume_number": 1, "title": volume.title, "summary": volume.summary,
        "chapter_range": "1-1", "source_hash": volume.source_hash}])
    import hashlib
    memory.extra["book_summary_sources"] = {
        "summary_hash": hashlib.sha256(memory.book_summary.encode()).hexdigest(),
        "contributing_sources": memory.extra["volume_summary_sources"]["1"]["contributing_sources"]}
    assert asyncio.run(service.update_book_summary("proj-1", user_id=1)) == "旧的全书摘要"
    service.llm_service.get_summary.assert_not_called()


def test_get_book_summary_returns_existing():
    """获取已有的书级摘要。"""
    existing_memory = SimpleNamespace(
        book_summary="已有的全书摘要",
        extra={},
    )

    session = _DummySession(execute_results=[
        _DummyResult(scalar=existing_memory),
    ])
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.get_book_summary("proj-1"))
    assert result == "已有的全书摘要"


def test_get_book_summary_returns_none_when_empty():
    """无书级摘要时返回 None。"""
    session = _DummySession(execute_results=[
        _DummyResult(scalar=None),
    ])
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.get_book_summary("proj-1"))
    assert result is None
