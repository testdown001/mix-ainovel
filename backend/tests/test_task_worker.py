import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api.routers import task_worker


@pytest.fixture(autouse=True)
def _stub_internal_secret(monkeypatch):
    monkeypatch.setattr(task_worker.settings, "task_dispatcher_internal_callback_secret", "s3cret")


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _NoopReporter:
    async def report(self, progress: int, stage: str, message: str):
        return None


def test_task_worker_uses_hybrid_executor_contract(monkeypatch):
    captured = {}
    fake_session = SimpleNamespace(commit=AsyncMock())
    fake_chapter = SimpleNamespace(id=42, status="not_generated")
    fake_novel_service = SimpleNamespace(
        ensure_project_owner=AsyncMock(return_value=SimpleNamespace(id="project-1")),
        get_or_create_chapter=AsyncMock(return_value=fake_chapter),
    )

    class _FakeHybridExecutor:
        def __init__(self, session, user_id):
            captured["session"] = session
            captured["user_id"] = user_id

        def enable_agent_system(self):
            captured["agent_enabled"] = True

        async def generate_chapter(self, **kwargs):
            captured["kwargs"] = kwargs
            return {
                "variants": [{"index": 0, "version_id": 7, "content": "正文"}],
                "best_version_index": 0,
                "preset": "agent",
            }

    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(fake_session))
    monkeypatch.setattr(task_worker, "NovelService", lambda session: fake_novel_service)
    monkeypatch.setattr(task_worker, "HybridExecutor", _FakeHybridExecutor)

    req = task_worker.WorkerTaskRequest(
        task_id="task-1",
        task_type="chapter:generate",
        project_id="project-1",
        chapter_number=3,
        user_id=12,
        config=task_worker.TaskConfig(
            preset="fast",
            use_agent_system=True,
            rag_mode="two_stage",
            writing_notes="提高张力",
            extra={
                "use_agentic_loop": True,
                "selected_skills": [{"skill_id": "dialogue"}],
            },
        ),
    )

    result = asyncio.run(task_worker._execute_chapter_generate(req, _NoopReporter()))

    fake_novel_service.ensure_project_owner.assert_awaited_once_with("project-1", 12)
    fake_novel_service.get_or_create_chapter.assert_awaited_once_with("project-1", 3)
    assert fake_chapter.status == "generating"
    assert captured["session"] is fake_session
    assert captured["user_id"] == 12
    assert captured["agent_enabled"] is True
    # 分阶段进度转发器(闭包)：断言传入且可调用，再校验其余 kwargs 契约不变
    _stream_handler = captured["kwargs"].pop("stream_handler", None)
    assert callable(_stream_handler)
    assert captured["kwargs"] == {
        "use_agent": True,
        "project_id": "project-1",
        "chapter_number": 3,
        "writing_notes": "提高张力",
        "flow_config": {
            "preset": "fast",
            "rag_mode": "two_stage",
            "use_agent": True,
            "use_agentic_loop": True,
            "selected_skills": [{"skill_id": "dialogue"}],
        },
    }
    assert result == {
        "chapter_id": 42,
        "chapter_number": 3,
        "status": "completed",
        "versions_count": 1,
        "best_version_index": 0,
        "preset": "agent",
    }


def test_batch_generate_auto_selects_best_version_and_reports_partial(monkeypatch):
    generate = AsyncMock(
        side_effect=[
            {"chapter_number": 7, "best_version_index": 2, "status": "completed"},
            RuntimeError("上游超时"),
        ]
    )
    select = AsyncMock(return_value=701)
    monkeypatch.setattr(task_worker, "_execute_chapter_generate", generate)
    monkeypatch.setattr(task_worker, "_select_batch_generated_chapter", select)

    req = task_worker.WorkerTaskRequest(
        task_id="task-batch",
        task_type="chapter:batch_generate",
        project_id="project-1",
        chapter_numbers=[7, 8],
        user_id=12,
        config=task_worker.TaskConfig(preset="fast"),
    )

    result = asyncio.run(task_worker._execute_batch_generate(req, _NoopReporter()))

    select.assert_awaited_once_with(req, 7, 2)
    assert result["status"] == "partial"
    assert result["total"] == 2
    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["results"][0]["result"]["selected_version_id"] == 701
    assert result["results"][1]["status"] == "failed"


def test_progress_reporter_sends_internal_secret(monkeypatch):
    captured = {}

    class _FakeClient:
        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs

        async def aclose(self):
            captured["closed"] = True

    monkeypatch.setattr(task_worker.httpx, "AsyncClient", lambda timeout: _FakeClient())
    monkeypatch.setattr(
        task_worker.settings,
        "task_dispatcher_internal_callback_secret",
        "shared-secret",
    )

    reporter = task_worker.ProgressReporter("http://gateway:3000/internal/tasks/task-1/progress", "task-1")
    asyncio.run(reporter.report(35, "llm_generation", "正在生成章节..."))
    asyncio.run(reporter.close())

    assert captured["url"] == "http://gateway:3000/internal/tasks/task-1/progress"
    assert captured["kwargs"]["headers"] == {"X-Internal-Secret": "shared-secret"}
    assert captured["kwargs"]["json"] == {
        "progress": 35,
        "stage": "llm_generation",
        "message": "正在生成章节...",
    }
    assert captured["closed"] is True


def test_execute_task_rejects_preset_above_tier(monkeypatch):
    # 异步入口与 /advanced/generate 同一套档位门控：free 用户提交 premium 任务必须被拒
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "get_user_tier", AsyncMock(return_value="free"))

    req = task_worker.WorkerTaskRequest(
        task_id="task-gate",
        task_type="chapter:generate",
        project_id="project-1",
        chapter_number=1,
        user_id=12,
        config=task_worker.TaskConfig(preset="premium"),
    )
    resp = asyncio.run(task_worker.execute_task(req, x_internal_secret="s3cret"))
    assert resp.status == "failed"
    assert "旗舰" in (resp.error or "")


def test_execute_task_gate_normalizes_alias(monkeypatch):
    # 旧名 platinum → premium，同样不能绕过门控
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "get_user_tier", AsyncMock(return_value="creator"))

    req = task_worker.WorkerTaskRequest(
        task_id="task-gate-alias",
        task_type="chapter:generate",
        project_id="project-1",
        chapter_number=1,
        user_id=12,
        config=task_worker.TaskConfig(preset="platinum"),
    )
    resp = asyncio.run(task_worker.execute_task(req, x_internal_secret="s3cret"))
    assert resp.status == "failed"
    assert "旗舰" in (resp.error or "")


def test_execute_task_gate_allows_free_fast(monkeypatch):
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "get_user_tier", AsyncMock(return_value="free"))
    monkeypatch.setattr(
        task_worker,
        "_execute_chapter_generate",
        AsyncMock(return_value={"status": "completed"}),
    )

    req = task_worker.WorkerTaskRequest(
        task_id="task-gate-ok",
        task_type="chapter:generate",
        project_id="project-1",
        chapter_number=1,
        user_id=12,
        config=task_worker.TaskConfig(preset="fast"),
    )
    resp = asyncio.run(task_worker.execute_task(req, x_internal_secret="s3cret"))
    assert resp.status == "completed"


def test_task_config_tolerates_null_fields_from_gateway():
    """Go 网关把 nil map/空值序列化为 JSON null(如 config.extra:null)；TaskConfig 非 Optional
    字段遇显式 null 本会 422。校验器应丢弃 null 项、回落默认值，避免 worker 拒收任务。"""
    from app.api.routers.task_worker import TaskConfig, WorkerTaskRequest

    cfg = TaskConfig.model_validate(
        {"preset": "standard", "extra": None, "writing_notes": None, "use_agent_system": None}
    )
    assert cfg.extra == {}
    assert cfg.writing_notes == ""
    assert cfg.use_agent_system is False
    assert cfg.preset == "standard"

    req = WorkerTaskRequest.model_validate(
        {
            "task_id": "t1",
            "task_type": "chapter_generate",
            "project_id": "p1",
            "chapter_number": 1,
            "user_id": 1,
            "config": {"preset": "fast", "extra": None},
        }
    )
    assert req.config.extra == {}
    assert req.config.preset == "fast"
