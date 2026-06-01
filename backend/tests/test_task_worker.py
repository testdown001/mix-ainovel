import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api.routers import task_worker


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
