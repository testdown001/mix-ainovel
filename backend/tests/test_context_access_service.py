import asyncio
from types import SimpleNamespace

from app.services.context_access_service import ContextAccessService


class _DummyScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _DummyExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return _DummyScalarResult(self._value)


class _DummySession:
    def __init__(self, value):
        self._value = value

    async def execute(self, stmt):
        return _DummyExecuteResult(self._value)


def test_context_access_service_get_project_memory_text():
    memory = SimpleNamespace(global_summary="全局摘要", plot_arcs={"主线": "推进"})
    service = ContextAccessService(_DummySession(memory), llm_service=None, prompt_service=None)

    text = asyncio.run(service.get_project_memory_text("proj-1"))

    assert "### 全局摘要" in text
    assert "剧情线追踪" in text


def test_context_access_service_prefetch_project_memory_text(monkeypatch):
    from app.services import context_access_service as module

    memory = SimpleNamespace(global_summary="背景总览", plot_arcs={"支线": "发酵"})

    class _SessionContext:
        async def __aenter__(self):
            return _DummySession(memory)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(module, "AsyncSessionLocal", lambda: _SessionContext())

    service = ContextAccessService(_DummySession(None), llm_service=None, prompt_service=None)
    text = asyncio.run(service.prefetch_project_memory_text("proj-2"))

    assert "背景总览" in text
    assert "支线" in text


def test_context_access_service_format_filtered_context():
    filtered = SimpleNamespace(
        plot_fuel=["情节A"],
        character_info=["角色B"],
        world_fragments=[],
        narrative_techniques=["技法C"],
        warnings=["警告D"],
    )

    text = ContextAccessService.format_filtered_context(filtered)

    assert "## 情节燃料" in text
    assert "角色B" in text
    assert "警告D" in text
