from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.routers.novels import _persist_concept_reference_titles
from app.models.novel import NovelProject
from app.models.reference_novel import ReferenceNovel
from app.services import reference_project_service as module
from app.services.reference_novel_library_service import ReferenceNovelLibraryService
from app.services.reference_reading_contract import fallback_dna, stamp


async def seed(session, *, second_status="ready"):
    session.add_all([
        ReferenceNovel(id=1, user_id=7, title="甲", status="ready", memory_card={"core_selling_point": "成长回报"}),
        ReferenceNovel(id=2, user_id=7, title="乙", status=second_status, memory_card={"core_selling_point": "关系牵挂"}),
        NovelProject(id="project-ref", user_id=7, title="本书", reference_novel_ids=[2, 1]),
    ])
    await session.commit()
    return async_sessionmaker(session.bind, expire_on_commit=False)


@pytest.mark.asyncio
async def test_title_input_persists_ready_and_new_books_in_user_order(db_session):
    await seed(db_session)
    project = await db_session.get(NovelProject, "project-ref")
    tasks = BackgroundTasks()
    service = ReferenceNovelLibraryService(db_session)
    await _persist_concept_reference_titles(project, ["甲", "新书", "乙"], 7, db_session, service, tasks)
    await db_session.refresh(project)
    bound = await service.get_by_ids(project.reference_novel_ids)
    assert [n.title for n in bound] == ["甲", "新书", "乙"]
    assert [n.status for n in bound] == ["ready", "pending", "ready"]
    assert len(tasks.tasks) == 1 and tasks.tasks[0].args == ("新书", 7)
    assert project.fusion_dna is None


@pytest.mark.asyncio
@pytest.mark.parametrize("second_status", ["pending", "analyzing", "failed", "missing"])
async def test_no_partial_fusion_when_one_source_is_unavailable(db_session, monkeypatch, second_status):
    factory = await seed(db_session, second_status=second_status)
    if second_status == "missing":
        project = await db_session.get(NovelProject, "project-ref")
        project.reference_novel_ids = [99, 1]
        await db_session.commit()
    generate = AsyncMock()
    monkeypatch.setattr(module.ReferenceNovelLibraryService, "generate_fusion_dna", generate)
    result = await module.refresh_project_fusion("project-ref", [99, 1] if second_status == "missing" else [2, 1], 7, factory)
    assert result is None
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_fresh_poll_observes_completion_and_reuses_cached_result(db_session, monkeypatch):
    factory = await seed(db_session, second_status="analyzing")
    calls = []

    async def complete(_seconds):
        async with factory() as session:
            await session.execute(update(ReferenceNovel).where(ReferenceNovel.id == 2).values(status="ready"))
            await session.commit()

    async def generate(self, novels, user_id):
        calls.append(([n.id for n in novels], user_id))
        return stamp(fallback_dna(novels), novels, generated=True)

    monkeypatch.setattr(module.asyncio, "sleep", complete)
    monkeypatch.setattr(module.ReferenceNovelLibraryService, "generate_fusion_dna", generate)
    dna = await module.refresh_project_fusion("project-ref", [2, 1], 7, factory, attempts=2)
    assert dna["source_ids"] == [2, 1]
    assert calls == [([2, 1], 7)]
    assert await module.refresh_project_fusion("project-ref", [2, 1], 7, factory) == dna
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["binding", "analysis"])
async def test_result_cannot_overwrite_changes_made_during_llm_call(db_session, monkeypatch, change):
    factory = await seed(db_session)

    async def generate(self, novels, user_id):
        async with factory() as session:
            if change == "binding":
                await session.execute(update(NovelProject).where(NovelProject.id == "project-ref").values(
                    reference_novel_ids=[1], fusion_dna={"new_selection": True}))
            else:
                await session.execute(update(ReferenceNovel).where(ReferenceNovel.id == 2).values(
                    memory_card={"core_selling_point": "新分析"}))
            await session.commit()
        return stamp(fallback_dna(novels), novels, generated=True)

    monkeypatch.setattr(module.ReferenceNovelLibraryService, "generate_fusion_dna", generate)
    assert await module.refresh_project_fusion("project-ref", [2, 1], 7, factory) is None
    await db_session.refresh(await db_session.get(NovelProject, "project-ref"))
    project = await db_session.get(NovelProject, "project-ref")
    assert project.fusion_dna == ({"new_selection": True} if change == "binding" else None)


@pytest.mark.asyncio
async def test_wrong_owner_does_not_generate_or_write_fusion(db_session, monkeypatch):
    factory = await seed(db_session)
    generate = AsyncMock()
    monkeypatch.setattr(module.ReferenceNovelLibraryService, "generate_fusion_dna", generate)
    assert await module.refresh_project_fusion("project-ref", [2, 1], 8, factory) is None
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_blueprint_and_chapter_loading_repair_legacy_fusion_once(db_session, monkeypatch):
    from app.db import session as session_module
    from app.services.blueprint_generation_service import _build_structure_reference
    from app.services.generation_support_service import GenerationSupportService

    factory = await seed(db_session)
    monkeypatch.setattr(session_module, "AsyncSessionLocal", factory)
    calls = []

    async def generate(self, novels, user_id):
        calls.append([n.id for n in novels])
        return stamp(fallback_dna(novels), novels, generated=True)

    monkeypatch.setattr(module.ReferenceNovelLibraryService, "generate_fusion_dna", generate)
    project = await db_session.get(NovelProject, "project-ref")
    project.fusion_dna = {"narrative_strategy": "旧版泛化融合"}
    await db_session.commit()
    text = await _build_structure_reference(db_session, project)
    assert "《乙》分工" in text and "《甲》分工" in text
    assert "情绪余波与后续牵挂" in text
    assert "旧版泛化融合" not in text
    # 下一次章节读取已升级的缓存，不再为同一组参考额外调用模型。
    novels = await GenerationSupportService(db_session).load_project_reference_novels(
        project, ReferenceNovelLibraryService(db_session))
    assert [n.id for n in novels] == [2, 1]
    assert calls == [[2, 1]]
