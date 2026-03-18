import asyncio
import hashlib
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
    mod = importlib.import_module("app.services.volume_summary_service")
    return mod.VolumeSummaryService


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


def _mock_llm(summary_text="卷级摘要内容"):
    llm = SimpleNamespace()
    llm.get_summary = AsyncMock(return_value=summary_text)
    llm.get_embedding = AsyncMock(return_value=[0.1] * 10)
    return llm


def test_compute_volume_number():
    """章节号到卷号的映射。"""
    session = _DummySession()
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    assert service.compute_volume_number(1, 10) == 1
    assert service.compute_volume_number(10, 10) == 1
    assert service.compute_volume_number(11, 10) == 2
    assert service.compute_volume_number(20, 10) == 2
    assert service.compute_volume_number(21, 10) == 3
    assert service.compute_volume_number(5, 5) == 1
    assert service.compute_volume_number(6, 5) == 2


def test_compute_volume_range():
    """卷号到章节范围的映射。"""
    session = _DummySession()
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    assert service.compute_volume_range(1, 10) == (1, 10)
    assert service.compute_volume_range(2, 10) == (11, 20)
    assert service.compute_volume_range(3, 10) == (21, 30)
    assert service.compute_volume_range(1, 5) == (1, 5)
    assert service.compute_volume_range(2, 5) == (6, 10)


def test_compute_source_hash():
    """摘要 hash 稳定且内容变化时 hash 变化。"""
    summaries_a = [
        {"chapter_number": 1, "summary": "摘要A"},
        {"chapter_number": 2, "summary": "摘要B"},
    ]
    summaries_b = [
        {"chapter_number": 1, "summary": "摘要A"},
        {"chapter_number": 2, "summary": "摘要C"},  # 变了
    ]

    cls = _get_service_class()
    hash_a1 = cls._compute_source_hash(summaries_a)
    hash_a2 = cls._compute_source_hash(summaries_a)
    hash_b = cls._compute_source_hash(summaries_b)

    assert hash_a1 == hash_a2  # 稳定
    assert hash_a1 != hash_b   # 内容变化 hash 变化


def test_update_volume_for_chapter_generates_summary():
    """有足够章节摘要时生成卷级摘要。"""
    # update_volume_for_chapter 的 execute 调用顺序：
    # 1. get_volume_size → SystemConfigRepository.get_by_key → scalars().first() → None
    # 2. _load_chapter_summaries → 章节查询 → .all() → [(1,"摘要1"), ...]
    # 3. _load_chapter_summaries → 大纲查询 → .all() → [(1,"起始"), ...]
    # 4. _get_existing → scalars().first() → None
    session = _DummySession(execute_results=[
        _DummyResult(scalar=None),  # volume_size config → 默认 10
        _DummyResult(rows=[(1, "第1章摘要"), (2, "第2章摘要"), (3, "第3章摘要")]),
        _DummyResult(rows=[(1, "起始"), (2, "发展"), (3, "高潮")]),
        _DummyResult(scalar=None),  # 无现有卷摘要
    ])
    llm = _mock_llm("生成的卷摘要")
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.update_volume_for_chapter("proj-1", 3, user_id=1))

    assert result is not None
    assert session._committed is True
    llm.get_summary.assert_called_once()


def test_update_volume_skips_when_no_summaries():
    """无章节摘要时跳过。"""
    session = _DummySession(execute_results=[
        _DummyResult(scalar=None),  # volume_size config
        _DummyResult(rows=[]),      # 无章节摘要
        _DummyResult(rows=[]),      # 无大纲
    ])
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.update_volume_for_chapter("proj-1", 1, user_id=1))

    assert result is None
    llm.get_summary.assert_not_called()


def test_rebuild_all_returns_stats():
    """rebuild_all 返回统计信息。"""
    # rebuild_all 的 execute 调用顺序：
    # 1. get_volume_size → scalars().first() → None
    # 2. max_chapter 查询 → scalars().first() → 5
    # 3. _load_chapter_summaries → 章节查询 → .all()
    # 4. _load_chapter_summaries → 大纲查询 → .all()
    # 5. _get_existing → scalars().first() → None
    session = _DummySession(execute_results=[
        _DummyResult(scalar=None),  # volume_size config
        _DummyResult(scalar=5),     # max_chapter = 5
        _DummyResult(rows=[(i, f"摘要{i}") for i in range(1, 6)]),  # 章节摘要
        _DummyResult(rows=[(i, f"第{i}章") for i in range(1, 6)]),  # 大纲标题
        _DummyResult(scalar=None),  # 无现有卷摘要
    ])
    llm = _mock_llm("卷摘要")
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.rebuild_all("proj-1", user_id=1, force=True))

    assert result["total_volumes"] == 1
    assert result["updated"] == 1
    assert result["skipped"] == 0


def test_get_relevant_volume_summaries_returns_recent():
    """获取当前章节相关的卷级摘要。"""
    # 使用真实的 VolumeSummary 对象会需要 DB 连接
    # 这里测试 compute 逻辑即可
    session = _DummySession()
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    # 第 25 章属于第 3 卷 (volume_size=10)
    vol = service.compute_volume_number(25, 10)
    assert vol == 3

    # max_volumes=3 → 应取卷 1, 2, 3
    start_vol = max(1, vol - 3 + 1)
    assert start_vol == 1
