"""叙事记忆摘要：卷级概要必须全量进入 LLM 输入（回归缩进 bug——append 落在 for 外只送最后一卷）。"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _ensure_models_loaded():
    """确保所有 ORM 模型在测试前加载完毕。"""
    import app.models  # noqa: F401
    import app.models.user_quota  # noqa: F401


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
        self._committed = False
        self.execute = AsyncMock(side_effect=self._execute_side_effect)

    async def _execute_side_effect(self, *args, **kwargs):
        if self._call_idx < len(self._results):
            result = self._results[self._call_idx]
            self._call_idx += 1
            return result
        return _DummyResult()

    def add(self, obj):
        pass

    async def commit(self):
        self._committed = True


def _get_service_class():
    from app.services.narrative_summary_service import NarrativeSummaryService
    return NarrativeSummaryService


def test_build_prompt_content_includes_all_volumes():
    """3 卷输入 → 构建的 prompt 文本包含全部 3 卷的标题与摘要。"""
    service = _get_service_class()(session=None, llm_service=None)
    volumes = [
        {"volume_number": 1, "title": "风起", "summary": "卷一：主角出山"},
        {"volume_number": 2, "title": None, "summary": "卷二：宗门大比"},
        {"volume_number": 3, "title": "潮落", "summary": "卷三：王朝倾覆"},
    ]
    chapters = [{"chapter_number": 1, "summary": "第1章摘要"}]

    content = service._build_prompt_content(chapters, volumes, [], None)

    assert "## 风起" in content
    assert "卷一：主角出山" in content
    assert "## 第2卷" in content  # title 为空回退到 第N卷
    assert "卷二：宗门大比" in content
    assert "## 潮落" in content
    assert "卷三：王朝倾覆" in content


def test_update_sends_all_volume_summaries_to_llm():
    """走 update 全链路：多卷时喂给 LLM 的 user_content 含全部卷概要。"""
    memory = SimpleNamespace(
        story_timeline_summary=None,
        extra={},
        project_id="proj-1",
        global_summary=None,
        plot_arcs=None,
    )
    chapter_rows = [(i, f"第{i}章摘要") for i in range(1, 6)]
    volume_rows = [
        (1, "风起", "卷一：主角出山"),
        (2, None, "卷二：宗门大比"),
        (3, "潮落", "卷三：王朝倾覆"),
    ]
    session = _DummySession(execute_results=[
        _DummyResult(rows=chapter_rows),   # _load_chapter_summaries
        _DummyResult(rows=volume_rows),    # _load_volume_summaries
        _DummyResult(rows=[]),             # _load_pending_causal_chains
        _DummyResult(scalar=memory),       # _get_or_create_memory → _get_memory
    ])
    llm = SimpleNamespace(get_grader_llm_response=AsyncMock(return_value="生成的叙事摘要"))
    service = _get_service_class()(session, llm)

    result = asyncio.run(service.update("proj-1", 5, user_id=1))

    assert result == "生成的叙事摘要"
    call_args = llm.get_grader_llm_response.call_args
    user_content = call_args.kwargs["conversation_history"][0]["content"]
    for fragment in ("## 风起", "卷一：主角出山", "## 第2卷", "卷二：宗门大比", "## 潮落", "卷三：王朝倾覆"):
        assert fragment in user_content
