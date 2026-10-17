"""External caches and legacy state cannot overrule the adopted manuscript."""
import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from mem0 import AsyncMemory

from app.models.user import User
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.memory_layer import CharacterState
from app.models.chapter_derivation import ChapterDerivationJob
from app.services.chapter_derivation_service import build_source_ref
from app.services.memory_provenance import filter_mem0_results
from app.services.memory_layer_service import MemoryLayerService
from app.services.mem0_compat import ProvenanceMemory
from app.services.memory_distillation_service import MemoryDistillationService


async def seed(session):
    session.add(User(id=9651, username="memory-source", email="source@example.com", hashed_password="test"))
    session.add(NovelProject(id="memory-source", user_id=9651, title="来源"))
    await session.flush()
    chapter = Chapter(project_id="memory-source", chapter_number=1, revision_id=1)
    session.add(chapter)
    await session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content="亲人获救。", metadata_={})
    session.add(version)
    await session.flush()
    chapter.selected_version_id = version.id
    chapter.content_hash = hashlib.sha256(version.content.encode()).hexdigest()
    await session.commit()
    source = await build_source_ref(session, project_id=chapter.project_id, chapter_number=1)
    job = ChapterDerivationJob(id="memory-job", project_id=chapter.project_id, chapter_id=chapter.id,
                              adoption_revision_id=1, kind="memory", status="completed",
                              source_ref=source.model_dump(), payload={}, result={})
    session.add(job)
    await session.commit()
    return chapter, version, job


@pytest.mark.asyncio
async def test_mem0_requires_current_source_completed_receipt_and_matching_text(db_session):
    chapter, version, job = await seed(db_session)
    text = "亲人获救。"
    job.result = {"memory_ids": ["ok"], "memory_hashes": {"ok": hashlib.sha256(text.encode()).hexdigest()}}
    await db_session.commit()
    item = {"id": "ok", "memory": text, "metadata": {
        **job.source_ref, "provenance_schema": 2, "source_derivation_id": job.id,
    }}
    rows = [item, {"id": "legacy", "memory": "亲人去世。"},
            {**item, "id": "orphan"}, {**item, "memory": "亲人去世。"}]
    assert await filter_mem0_results(db_session, rows, chapter.project_id, 2) == [item]
    assert await filter_mem0_results(db_session, rows, chapter.project_id, 1) == []
    original_source = dict(job.source_ref)
    job.source_ref = {**original_source, "source_content_hash": "different-source"}
    await db_session.commit()
    assert await filter_mem0_results(db_session, [item], chapter.project_id, 2) == []
    job.source_ref = original_source
    job.status = "running"
    await db_session.commit()
    assert await filter_mem0_results(db_session, [item], chapter.project_id, 2) == []
    job.status = "completed"
    chapter.revision_id = 2
    await db_session.commit()
    assert await filter_mem0_results(db_session, [item], chapter.project_id, 2) == []


@pytest.mark.asyncio
async def test_legacy_and_future_character_states_do_not_enter_prompt(db_session):
    chapter, version, job = await seed(db_session)
    db_session.add_all([
        CharacterState(project_id=chapter.project_id, chapter_number=1, character_name="legacy", location="墓地"),
        CharacterState(project_id=chapter.project_id, chapter_number=1, character_name="valid", location="家中",
                       extra={"provenance": {**job.source_ref, "source_derivation_id": job.id}}),
        CharacterState(project_id=chapter.project_id, chapter_number=40, character_name="future", location="战场"),
    ])
    await db_session.commit()
    context = await MemoryLayerService(db_session).build_chapter_state_context(chapter.project_id, 2)
    assert "家中" in context
    assert "墓地" not in context and "战场" not in context


@pytest.mark.asyncio
async def test_pinned_mem0_infer_false_reuses_the_embedding():
    memory = object.__new__(ProvenanceMemory)
    with patch.object(AsyncMemory, "_create_memory", new_callable=AsyncMock, return_value="id") as create:
        assert await memory._create_memory("fact", [0.1, 0.2], {"source": 1}) == "id"
        create.assert_awaited_once_with("fact", {"fact": [0.1, 0.2]}, {"source": 1})


@pytest.mark.asyncio
async def test_v2_memories_never_enter_legacy_semantic_distillation():
    svc = MemoryDistillationService(AsyncMock())
    memory = AsyncMock()
    memory.get_all.return_value = {"results": [{"id": "v2", "metadata": {"provenance_schema": 2}}]}
    svc._memory = memory
    assert not await svc.should_distill("p")
    assert (await svc.distill("p", user_id=1))["reason"] == "version_bound_memories"
    memory.delete.assert_not_awaited()
    memory.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_derived_memory_failure_is_not_reported_as_completed():
    svc = MemoryLayerService(AsyncMock())
    svc.extract_character_states_from_chapter = AsyncMock(side_effect=RuntimeError("provider failed"))
    with patch("app.services.memory_layer_service.require_current_source", new_callable=AsyncMock):
        with pytest.raises(RuntimeError, match="provider failed"):
            await svc.update_state_after_chapter("p", 1, "正文", [], 1, source_ref={"project_id": "p"})


@pytest.mark.asyncio
async def test_mem0_add_failure_propagates_to_retryable_derivation():
    svc = MemoryLayerService(AsyncMock())
    svc.update_state_after_chapter = AsyncMock(return_value={})
    svc._extract_mem0_facts = AsyncMock(return_value=["事实"])
    memory = AsyncMock()
    memory.add.side_effect = TimeoutError("cache write failed")
    svc._memory = memory
    async def checkpoint(name, producer):
        return await producer()
    svc._extraction_checkpoint = checkpoint
    with patch("app.services.memory_layer_service.require_current_source", new_callable=AsyncMock):
        with pytest.raises(TimeoutError, match="cache write failed"):
            await svc.update_memory_after_chapter("p", 1, "事实", [], 1,
                source_ref={"project_id": "p", "source_derivation_id": "job"})
    assert memory.add.await_args.kwargs["infer"] is False
