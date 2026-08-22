import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import BackgroundTasks

from app.api.routers import novels as novels_router
from app.schemas.reference_novel import ReferenceNovelSelectRequest


def test_bind_waits_for_all_reference_novels_before_generating_fusion_dna(monkeypatch):
    project = SimpleNamespace(reference_novel_ids=[99], fusion_dna={"stale": True})
    available = {
        11: SimpleNamespace(id=11, status="ready"),
        22: SimpleNamespace(id=22, status="analyzing"),
    }
    generate_fusion_dna = AsyncMock()

    class _NovelService:
        def __init__(self, _session):
            pass

        async def ensure_project_owner(self, project_id, user_id):
            assert project_id == "project-1"
            assert user_id == 7
            return project

    class _ReferenceService:
        def __init__(self, _session):
            pass

        async def get_by_id(self, novel_id):
            return available.get(novel_id)

        async def generate_fusion_dna(self, novels, user_id):
            return await generate_fusion_dna(novels, user_id)

    monkeypatch.setattr(novels_router, "NovelService", _NovelService)
    monkeypatch.setattr(novels_router, "ReferenceNovelLibraryService", _ReferenceService)

    session = SimpleNamespace(commit=AsyncMock())
    background_tasks = BackgroundTasks()
    result = asyncio.run(
        novels_router.bind_project_reference_novels(
            "project-1",
            ReferenceNovelSelectRequest(reference_novel_ids=[11, 11, 22]),
            background_tasks,
            session,
            SimpleNamespace(id=7),
        )
    )

    assert result == {"status": "success", "bound_ids": [11, 22], "fusion_dna_ready": False}
    assert project.reference_novel_ids == [11, 22]
    assert project.fusion_dna is None
    generate_fusion_dna.assert_not_awaited()
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].args == ("project-1", [11, 22], 7)
    session.commit.assert_awaited_once()


def test_bind_generates_fusion_dna_from_the_complete_ready_set(monkeypatch):
    project = SimpleNamespace(reference_novel_ids=[], fusion_dna=None)
    available = {
        11: SimpleNamespace(id=11, status="ready"),
        22: SimpleNamespace(id=22, status="ready"),
    }
    generated = {"positioning": "融合定位"}
    generate_fusion_dna = AsyncMock(return_value=generated)

    class _NovelService:
        def __init__(self, _session):
            pass

        async def ensure_project_owner(self, _project_id, _user_id):
            return project

    class _ReferenceService:
        def __init__(self, _session):
            pass

        async def get_by_id(self, novel_id):
            return available.get(novel_id)

        async def generate_fusion_dna(self, novels, user_id):
            return await generate_fusion_dna(novels, user_id)

    monkeypatch.setattr(novels_router, "NovelService", _NovelService)
    monkeypatch.setattr(novels_router, "ReferenceNovelLibraryService", _ReferenceService)

    session = SimpleNamespace(commit=AsyncMock())
    background_tasks = BackgroundTasks()
    result = asyncio.run(
        novels_router.bind_project_reference_novels(
            "project-1",
            ReferenceNovelSelectRequest(reference_novel_ids=[11, 22]),
            background_tasks,
            session,
            SimpleNamespace(id=7),
        )
    )

    assert result["fusion_dna_ready"] is True
    assert project.fusion_dna == generated
    generate_fusion_dna.assert_awaited_once_with([available[11], available[22]], 7)
    assert background_tasks.tasks == []
