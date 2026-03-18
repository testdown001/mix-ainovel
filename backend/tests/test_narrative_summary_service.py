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
    mod = importlib.import_module("app.services.narrative_summary_service")
    return mod.NarrativeSummaryService


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

    def scalar(self):
        return self._scalar


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


def _make_memory(story_timeline_summary=None, extra=None):
    return SimpleNamespace(
        story_timeline_summary=story_timeline_summary,
        extra=extra or {},
        project_id="proj-1",
        global_summary=None,
        plot_arcs=None,
    )


def _mock_llm(response_text="生成的叙事摘要", *, grader_configured=True, raise_error=False):
    llm = SimpleNamespace()
    if grader_configured:
        if raise_error:
            llm.get_grader_llm_response = AsyncMock(side_effect=RuntimeError("LLM error"))
        else:
            llm.get_grader_llm_response = AsyncMock(return_value=response_text)
    else:
        async def _no_grader(*args, **kwargs):
            raise ValueError("证据评分模型未配置")
        llm.get_grader_llm_response = _no_grader
    return llm


# ------------------------------------------------------------------
# test_should_update
# ------------------------------------------------------------------


def test_should_update_false_when_gap_too_small():
    """间隔 < 5 章返回 False（无转折点事件）。"""
    # should_update 调用：
    # 1. _get_memory → scalars().first() → memory with last_chapter=3
    # 2. _has_turning_point_since → scalar() → 0
    memory = _make_memory(
        story_timeline_summary="已有摘要",
        extra={"narrative_summary_chapter": 3},
    )
    session = _DummySession(execute_results=[
        _DummyResult(scalar=memory),  # _get_memory
        _DummyResult(scalar=0),       # _has_turning_point_since → count=0
    ])
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.should_update("proj-1", 5))  # gap=2 < 5
    assert result is False


def test_should_update_true_at_interval():
    """间隔 >= 5 章返回 True。"""
    memory = _make_memory(
        story_timeline_summary="已有摘要",
        extra={"narrative_summary_chapter": 3},
    )
    session = _DummySession(execute_results=[
        _DummyResult(scalar=memory),  # _get_memory
    ])
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.should_update("proj-1", 8))  # gap=5 >= 5
    assert result is True


def test_should_update_true_on_turning_point():
    """有转折点事件时返回 True（即使间隔不够）。"""
    memory = _make_memory(
        story_timeline_summary="已有摘要",
        extra={"narrative_summary_chapter": 5},
    )
    session = _DummySession(execute_results=[
        _DummyResult(scalar=memory),  # _get_memory
        _DummyResult(scalar=1),       # _has_turning_point_since → count=1
    ])
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.should_update("proj-1", 7))  # gap=2 < 5, 但有转折
    assert result is True


def test_should_update_true_initial_generation():
    """首次生成：无摘要且 chapter >= 3 返回 True。"""
    session = _DummySession(execute_results=[
        _DummyResult(scalar=None),  # _get_memory → 无 ProjectMemory
    ])
    llm = _mock_llm()
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.should_update("proj-1", 3))
    assert result is True


# ------------------------------------------------------------------
# test_update
# ------------------------------------------------------------------


def test_initial_generation_uses_all_summaries():
    """首次生成时，发送全量章节摘要给 LLM。"""
    memory = _make_memory(story_timeline_summary=None, extra={})
    chapter_rows = [(i, f"第{i}章摘要") for i in range(1, 6)]

    session = _DummySession(execute_results=[
        # update 调用 _load_chapter_summaries
        _DummyResult(rows=chapter_rows),
        # _load_volume_summaries
        _DummyResult(rows=[]),
        # _load_pending_causal_chains
        _DummyResult(rows=[]),
        # _get_or_create_memory → _get_memory
        _DummyResult(scalar=memory),
    ])
    llm = _mock_llm("全新叙事摘要")
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.update("proj-1", 5, user_id=1))

    assert result == "全新叙事摘要"
    llm.get_grader_llm_response.assert_called_once()
    # 验证 prompt 中包含 "全部章节摘要"
    call_args = llm.get_grader_llm_response.call_args
    user_content = call_args.kwargs.get("conversation_history", call_args[1] if len(call_args[0]) > 1 else [{}])[0]["content"]
    assert "全部章节摘要" in user_content


def test_incremental_includes_old_summary():
    """增量更新时，prompt 中包含旧的叙事摘要。"""
    memory = _make_memory(
        story_timeline_summary="旧的叙事摘要内容",
        extra={"narrative_summary_hash": "old_hash", "narrative_summary_chapter": 5},
    )
    # 超过 10 章触发增量模式
    chapter_rows = [(i, f"第{i}章摘要") for i in range(1, 16)]

    session = _DummySession(execute_results=[
        # _load_chapter_summaries
        _DummyResult(rows=chapter_rows),
        # _load_volume_summaries
        _DummyResult(rows=[]),
        # _load_pending_causal_chains
        _DummyResult(rows=[]),
        # _get_or_create_memory → _get_memory
        _DummyResult(scalar=memory),
    ])
    llm = _mock_llm("增量更新后的摘要")
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.update("proj-1", 15, user_id=1))

    assert result == "增量更新后的摘要"
    llm.get_grader_llm_response.assert_called_once()
    call_args = llm.get_grader_llm_response.call_args
    user_content = call_args.kwargs.get("conversation_history", call_args[1] if len(call_args[0]) > 1 else [{}])[0]["content"]
    assert "旧的叙事摘要内容" in user_content
    assert "最近章节摘要" in user_content


def test_grader_not_configured_skips():
    """grader 未配置时静默跳过，不抛异常。"""
    memory = _make_memory(story_timeline_summary=None, extra={})
    chapter_rows = [(i, f"第{i}章摘要") for i in range(1, 6)]

    session = _DummySession(execute_results=[
        _DummyResult(rows=chapter_rows),
        _DummyResult(rows=[]),
        _DummyResult(rows=[]),
        _DummyResult(scalar=memory),
    ])
    llm = _mock_llm(grader_configured=False)
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.update("proj-1", 5, user_id=1))

    assert result is None
    assert session._committed is False  # 未写入 DB


def test_hash_skip_when_unchanged():
    """hash 相同时跳过更新。"""
    cls = _get_service_class()

    # 先算出 hash
    chapter_summaries = [{"chapter_number": i, "summary": f"摘要{i}"} for i in range(1, 4)]
    expected_hash = cls._compute_hash(chapter_summaries, [], [])

    memory = _make_memory(
        story_timeline_summary="已有摘要",
        extra={"narrative_summary_hash": expected_hash, "narrative_summary_chapter": 3},
    )

    session = _DummySession(execute_results=[
        # _load_chapter_summaries
        _DummyResult(rows=[(i, f"摘要{i}") for i in range(1, 4)]),
        # _load_volume_summaries
        _DummyResult(rows=[]),
        # _load_pending_causal_chains
        _DummyResult(rows=[]),
        # _get_or_create_memory → _get_memory
        _DummyResult(scalar=memory),
    ])
    llm = _mock_llm()
    service = cls(session, llm)

    result = asyncio.run(service.update("proj-1", 8, user_id=1))

    assert result is None  # hash 相同，跳过
    assert not hasattr(llm, 'get_grader_llm_response') or (
        hasattr(llm.get_grader_llm_response, 'call_count') and
        llm.get_grader_llm_response.call_count == 0
    )
