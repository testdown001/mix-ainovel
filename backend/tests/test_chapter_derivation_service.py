"""Canon adoption, durable outbox, source lineage and index activation contracts."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.chapter_derivation import ChapterDerivationJob
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.project_memory import ProjectMemory
from app.models.user import User
from app.services.chapter_derivation_service import (
    ChapterDerivationService, SupersededDerivation, build_source_ref,
    execute_derivation_job, source_is_current,
)
from app.services.chapter_revision_service import ChapterRevisionService, hash_chapter_content
from app.services.chapter_post_processor import ChapterPostProcessor


async def seed(session):
    session.add(User(id=9601, username="canon", email="canon@example.com", hashed_password="test"))
    session.add(NovelProject(id="canon-project", user_id=9601, title="正史测试"))
    await session.flush()
    chapter = Chapter(project_id="canon-project", chapter_number=1)
    session.add(chapter)
    await session.flush()
    versions = [ChapterVersion(chapter_id=chapter.id, content=text, source="generation", metadata_={
        "derivation_profile": {"state": True, "foreshadowing": True},
    }) for text in ("亲人去世。", "亲人获救。")]
    session.add_all(versions)
    await session.commit()
    return chapter, versions


@pytest.mark.asyncio
async def test_candidates_do_not_enqueue_and_repeated_adoption_is_idempotent(db_session):
    chapter, versions = await seed(db_session)
    assert (await db_session.execute(select(ChapterDerivationJob))).scalars().all() == []
    service = ChapterRevisionService(db_session)
    adopted = await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id)
    jobs = (await db_session.execute(select(ChapterDerivationJob))).scalars().all()
    assert {job.kind for job in jobs} == {
        "summary", "index", "volume_summary", "book_summary", "narrative_summary",
        "character_significance", "state", "foreshadowing",
    }
    assert all(job.source_ref["source_version_id"] == versions[1].id for job in jobs)
    retried = await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id)
    assert retried.revision.revision_id == adopted.revision.revision_id
    assert len((await db_session.execute(select(ChapterDerivationJob))).scalars().all()) == len(jobs)


@pytest.mark.asyncio
async def test_overwriting_adoption_requires_baseline_and_conflicts_leave_no_jobs(db_session):
    chapter, versions = await seed(db_session)
    service = ChapterRevisionService(db_session)
    first = await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    with pytest.raises(Exception) as missing:
        await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id)
    assert missing.value.status_code == 428
    with pytest.raises(Exception) as conflict:
        await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id,
                            expected_revision_id=0, expected_content_hash=hash_chapter_content(""))
    assert conflict.value.status_code == 409
    assert all(job.adoption_revision_id == first.revision.revision_id for job in (
        await db_session.execute(select(ChapterDerivationJob))).scalars())


@pytest.mark.asyncio
async def test_manual_save_queues_existing_postprocess_but_not_extra_extraction(db_session):
    chapter, versions = await seed(db_session)
    service = ChapterRevisionService(db_session)
    first = await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    result = await service.save(project_id=chapter.project_id, chapter_number=1, content="亲人只是失踪。",
                                expected_revision_id=first.revision.revision_id,
                                expected_content_hash=first.revision.content_hash)
    jobs = (await db_session.execute(select(ChapterDerivationJob).where(
        ChapterDerivationJob.adoption_revision_id == result.revision.revision_id))).scalars().all()
    assert not {"memory", "state", "foreshadowing"} & {job.kind for job in jobs}
    repeated = await service.save(project_id=chapter.project_id, chapter_number=1, content="亲人只是失踪。",
                                  expected_revision_id=result.revision.revision_id,
                                  expected_content_hash=result.revision.content_hash)
    assert repeated.revision.revision_id == result.revision.revision_id


@pytest.mark.asyncio
async def test_outbox_enqueue_and_adoption_rollback_together(db_session, monkeypatch):
    chapter, versions = await seed(db_session)
    async def fail_commit():
        raise RuntimeError("injected database commit failure")
    real_commit = db_session.commit
    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        await ChapterRevisionService(db_session).adopt(
            project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    await db_session.rollback()
    monkeypatch.setattr(db_session, "commit", real_commit)
    current = await ChapterRevisionService(db_session).get_revision("canon-project", 1)
    assert current.selected_version_id is None
    assert (await db_session.execute(select(ChapterDerivationJob))).scalars().all() == []


@pytest.mark.asyncio
async def test_source_checks_reject_other_candidate_and_changed_earlier_lineage(db_session):
    chapter, versions = await seed(db_session)
    revision = ChapterRevisionService(db_session)
    first = await revision.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    source = await build_source_ref(db_session, project_id=chapter.project_id, chapter_number=1)
    assert await source_is_current(db_session, source)
    chapter_two = Chapter(project_id=chapter.project_id, chapter_number=2)
    db_session.add(chapter_two)
    await db_session.flush()
    second = ChapterVersion(chapter_id=chapter_two.id, content="第二章正文")
    db_session.add(second)
    await db_session.flush()
    await revision.adopt(project_id=chapter.project_id, chapter_number=2, version_id=second.id)
    future_source = await build_source_ref(db_session, project_id=chapter.project_id, chapter_number=2)
    chapter_two.active_index_revision_id, chapter_two.rag_ingest_hash = "future-index", "future-ingest"
    await db_session.commit()
    await revision.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id,
                         expected_revision_id=first.revision.revision_id,
                         expected_content_hash=first.revision.content_hash)
    assert not await source_is_current(db_session, source)
    assert not await source_is_current(db_session, future_source)
    await db_session.refresh(chapter_two)
    assert chapter_two.active_index_revision_id is None and chapter_two.rag_ingest_hash is None
    future_jobs = (await db_session.execute(select(ChapterDerivationJob).where(
        ChapterDerivationJob.chapter_id == chapter_two.id))).scalars().all()
    assert all(job.status == "superseded" for job in future_jobs)


@pytest.mark.asyncio
async def test_database_lease_single_owner_and_expired_restart_recovery(db_session):
    chapter, versions = await seed(db_session)
    await ChapterRevisionService(db_session).adopt(
        project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    service = ChapterDerivationService(db_session)
    job = await service.claim_next("worker-a")
    assert job.status == "running" and job.attempts == 1
    job_id = job.id
    claimed = await service.claim_next("worker-b")
    assert not claimed or claimed.id != job_id
    expired = await db_session.get(ChapterDerivationJob, job_id)
    expired.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    await db_session.commit()
    recovered_ids = []
    for _ in range(8):
        recovered = await service.claim_next("worker-restarted")
        if recovered:
            recovered_ids.append(recovered.id)
        if job_id in recovered_ids:
            break
    assert job_id in recovered_ids
    await service.finish(job_id, "old-worker", status="completed")
    await db_session.refresh(expired)
    assert expired.lease_owner == "worker-restarted"


@pytest.mark.asyncio
async def test_late_summary_is_checkpointed_but_never_published(db_session):
    chapter, versions = await seed(db_session)
    service = ChapterRevisionService(db_session)
    first = await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    job = (await db_session.execute(select(ChapterDerivationJob).where(
        ChapterDerivationJob.kind == "summary"))).scalar_one()
    async def summary(*args, **kwargs):
        await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id,
                            expected_revision_id=first.revision.revision_id,
                            expected_content_hash=first.revision.content_hash)
        return "失效摘要"
    processor = ChapterPostProcessor(db_session, SimpleNamespace(get_summary=summary))
    with pytest.raises(SupersededDerivation):
        await processor._ensure_summary(chapter.project_id, 1, versions[0].content, 9601,
                                        source_ref=job.source_ref, derivation_job_id=job.id)
    await db_session.refresh(chapter)
    assert chapter.real_summary is None
    await db_session.refresh(job)
    assert job.result["summary"] == "失效摘要"


@pytest.mark.asyncio
async def test_index_failure_does_not_advance_ingest_or_active_revision(db_session, monkeypatch):
    from app.services.chapter_ingest_service import ChapterIngestionService
    chapter, versions = await seed(db_session)
    await ChapterRevisionService(db_session).adopt(
        project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id)
    monkeypatch.setattr(ChapterIngestionService, "ingest_chapter", AsyncMock(side_effect=RuntimeError("offline")))
    processor = ChapterPostProcessor(db_session, SimpleNamespace())
    with pytest.raises(RuntimeError):
        await processor._ingest_and_hash(chapter.project_id, 1, versions[1].content, 9601, strict=True)
    await db_session.refresh(chapter)
    assert chapter.rag_ingest_hash is None and chapter.active_index_revision_id is None


@pytest.mark.asyncio
async def test_finish_preserves_extraction_checkpoint(db_session):
    chapter, versions = await seed(db_session)
    await ChapterRevisionService(db_session).adopt(
        project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    service = ChapterDerivationService(db_session)
    job = await service.claim_next("owner")
    job.result = {"extraction_state": {"facts": ["f"]}}
    await db_session.commit()
    await service.finish(job.id, "owner", status="completed", result={"memory_ids": ["m"]})
    await db_session.refresh(job)
    assert job.result == {"extraction_state": {"facts": ["f"]}, "memory_ids": ["m"]}


@pytest.mark.asyncio
async def test_late_index_receipt_cannot_activate_superseded_text(db_session, monkeypatch):
    from app.services.chapter_ingest_service import ChapterIngestionService, IngestionReceipt
    chapter, versions = await seed(db_session)
    service = ChapterRevisionService(db_session)
    first = await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    async def staging(self, **kwargs):
        assert kwargs["source_ref"]["source_version_id"] == versions[0].id
        await service.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id,
                            expected_revision_id=first.revision.revision_id,
                            expected_content_hash=first.revision.content_hash)
        return IngestionReceipt("orphan-staging-revision", 1, 0, "degraded")
    monkeypatch.setattr(ChapterIngestionService, "ingest_chapter", staging)
    processor = ChapterPostProcessor(db_session, SimpleNamespace())
    with pytest.raises(SupersededDerivation):
        await processor._ingest_and_hash(chapter.project_id, 1, versions[0].content, 9601, strict=True)
    await db_session.refresh(chapter)
    assert chapter.selected_version_id == versions[1].id
    assert chapter.active_index_revision_id is None and chapter.rag_ingest_hash is None


@pytest.mark.asyncio
async def test_summary_snapshot_reuses_one_call_and_is_idempotent(db_session):
    from app.models.project_memory import ChapterSnapshot
    chapter, versions = await seed(db_session)
    await ChapterRevisionService(db_session).adopt(
        project_id=chapter.project_id, chapter_number=1, version_id=versions[1].id)
    llm = SimpleNamespace(get_summary=AsyncMock(return_value="亲人在危急关头获救。"))
    processor = ChapterPostProcessor(db_session, llm)
    result = await processor._ensure_summary(chapter.project_id, 1, versions[1].content, 9601)
    await processor._ensure_summary(chapter.project_id, 1, versions[1].content, 9601)
    assert result == "亲人在危急关头获救。"
    llm.get_summary.assert_awaited_once()
    memory = (await db_session.execute(select(ProjectMemory))).scalar_one()
    assert memory.extra["chapter_summary_sources"]["1"]["source_ref"]["source_version_id"] == versions[1].id
    snapshots = (await db_session.execute(select(ChapterSnapshot))).scalars().all()
    assert len(snapshots) == 1 and snapshots[0].chapter_summary == result


@pytest.mark.asyncio
async def test_worker_retains_generation_baseline_when_author_saves_mid_generation(db_session, monkeypatch):
    from app.api.routers import task_worker
    from app.services.cache_service import CacheService
    chapter, versions = await seed(db_session)
    revisions = ChapterRevisionService(db_session)
    baseline = await revisions.adopt(project_id=chapter.project_id, chapter_number=1, version_id=versions[0].id)
    class Context:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, *args):
            return None
    class Executor:
        def __init__(self, *args, **kwargs):
            pass
        async def generate_chapter(self, **kwargs):
            await revisions.save(project_id=chapter.project_id, chapter_number=1, content="作者在生成期间亲手修改。",
                                 expected_revision_id=baseline.revision.revision_id,
                                 expected_content_hash=baseline.revision.content_hash)
            return {"variants": [{"index": 0, "version_id": versions[1].id, "content": versions[1].content}],
                    "best_version_index": 0, "preset": "fast"}
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", Context)
    monkeypatch.setattr(task_worker, "HybridExecutor", Executor)
    monkeypatch.setattr(CacheService, "invalidate_project_schema_safely", AsyncMock())
    req = task_worker.WorkerTaskRequest(task_id="cas-test", task_type="chapter:generate",
        project_id=chapter.project_id, chapter_number=1, user_id=9601,
        config=task_worker.TaskConfig(preset="fast", auto_select=True))
    reporter = SimpleNamespace(report=AsyncMock())
    result = await task_worker._execute_chapter_generate(req, reporter)
    assert result["adoption_baseline"]["revision_id"] == baseline.revision.revision_id
    assert result["best_version_id"] == versions[1].id
    with pytest.raises(Exception) as conflict:
        await task_worker._select_batch_generated_chapter(req, 1, 0,
            version_id=result["best_version_id"], adoption_baseline=result["adoption_baseline"],
            schedule_next_mission=False, schedule_post_process=False)
    assert conflict.value.status_code == 409
    current = await revisions.get_revision(chapter.project_id, 1)
    assert current.content == "作者在生成期间亲手修改。"


@pytest.mark.asyncio
async def test_more_than_one_page_of_terminal_dependencies_cannot_starve_healthy_work(db_session):
    from uuid import uuid4
    chapter, versions = await seed(db_session)
    blocked_ids = []
    for number in range(2, 203):
        row = Chapter(project_id=chapter.project_id, chapter_number=number)
        db_session.add(row)
        await db_session.flush()
        source = {"project_id": chapter.project_id, "chapter_id": row.id, "chapter_number": number,
                  "source_version_id": versions[0].id, "source_content_hash": "h",
                  "adoption_revision_id": 1, "narrative_base": "b"}
        db_session.add(ChapterDerivationJob(id=str(uuid4()), project_id=chapter.project_id,
            chapter_id=row.id, adoption_revision_id=1, kind="volume_summary", source_ref=source,
            payload={}, status="failed", attempts=3, max_attempts=3))
        job = ChapterDerivationJob(id=str(uuid4()), project_id=chapter.project_id, chapter_id=row.id,
            adoption_revision_id=1, kind="book_summary", source_ref=source,
            payload={"depends_on": ["volume_summary"]}, status="queued")
        db_session.add(job)
        blocked_ids.append(job.id)
    healthy = ChapterDerivationJob(id=str(uuid4()), project_id=chapter.project_id, chapter_id=chapter.id,
        adoption_revision_id=1, kind="state", source_ref={}, payload={}, status="queued")
    db_session.add(healthy)
    await db_session.commit()
    healthy_id = healthy.id
    claimed = await ChapterDerivationService(db_session).claim_next("healthy-worker")
    assert claimed.id == healthy_id
    statuses = (await db_session.execute(select(ChapterDerivationJob.status).where(
        ChapterDerivationJob.id.in_(blocked_ids)))).scalars().all()
    assert len(statuses) == 201 and set(statuses) == {"cancelled"}
