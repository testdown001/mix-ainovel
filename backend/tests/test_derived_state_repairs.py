from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.chapter_derivation import ChapterDerivationJob
from app.models.derived_state_repair import DerivedStateRepair
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.user import User
from app.services.chapter_derivation_service import ChapterDerivationService
from app.services.chapter_revision_service import ChapterRevisionService
from app.services.derived_state_repair_service import (
    DerivedStateRepairService, PlatformRepairLLM, RepairBudgetExceeded,
    process_repair, repair_narrative_delta,
)
from app.services.llm_service import LLMService


async def seed(session):
    session.add(User(id=9901, username="repair-admin", email="repair@example.com", hashed_password="hash", is_admin=True))
    session.add(NovelProject(id="repair-project", user_id=9901, title="平台修复"))
    await session.flush()
    chapter = Chapter(project_id="repair-project", chapter_number=1)
    session.add(chapter)
    await session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content="秦川发现姐姐还活着。", source="generation")
    session.add(version)
    await session.flush()
    adopted = await ChapterRevisionService(session).adopt(
        project_id=chapter.project_id, chapter_number=1, version_id=version.id)
    return chapter, version, adopted


@pytest.mark.asyncio
async def test_estimate_is_dormant_and_requires_creator_token_explicit_budget(db_session, monkeypatch):
    await seed(db_session)
    outbound = AsyncMock()
    monkeypatch.setattr(LLMService, "get_llm_response", outbound)
    service = DerivedStateRepairService(db_session)
    estimate = await service.estimate(project_id="repair-project", admin_user_id=9901,
        chapter_start=1, chapter_end=1, kinds=["summary"])
    assert estimate["status"] == "estimated" and estimate["budget_tokens"] == 0
    assert estimate["estimated_upper_tokens"] > 0
    outbound.assert_not_awaited()
    with pytest.raises(Exception) as missing:
        await service.start(project_id="repair-project", repair_id=estimate["id"], admin_user_id=9901,
            estimate_token=estimate["estimate_token"], platform_budget_tokens=10000, confirm_platform_budget=False)
    assert missing.value.status_code == 428
    with pytest.raises(Exception) as forged:
        await service.start(project_id="repair-project", repair_id=estimate["id"], admin_user_id=9901,
            estimate_token="0" * 64, platform_budget_tokens=10000, confirm_platform_budget=True)
    assert forged.value.status_code == 403
    outbound.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_rejects_changed_source_fingerprint(db_session):
    chapter, version, adopted = await seed(db_session)
    service = DerivedStateRepairService(db_session)
    estimate = await service.estimate(project_id=chapter.project_id, admin_user_id=9901,
        chapter_start=1, chapter_end=1, kinds=["narrative_delta"])
    await ChapterRevisionService(db_session).save(project_id=chapter.project_id, chapter_number=1,
        content="秦川发现姐姐已经离开。", expected_revision_id=adopted.revision.revision_id,
        expected_content_hash=adopted.revision.content_hash)
    with pytest.raises(Exception) as stale:
        await service.start(project_id=chapter.project_id, repair_id=estimate["id"], admin_user_id=9901,
            estimate_token=estimate["estimate_token"], platform_budget_tokens=100000, confirm_platform_budget=True)
    assert stale.value.status_code == 409


async def authorized(session, *, budget=200000, kinds=None):
    service = DerivedStateRepairService(session)
    estimate = await service.estimate(project_id="repair-project", admin_user_id=9901,
        chapter_start=1, chapter_end=1, kinds=kinds or ["summary"])
    result = await service.start(project_id="repair-project", repair_id=estimate["id"], admin_user_id=9901,
        estimate_token=estimate["estimate_token"], platform_budget_tokens=budget, confirm_platform_budget=True)
    repair = await session.get(DerivedStateRepair, result["id"])
    repair.status, repair.lease_owner = "running", "test-owner"
    repair.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=900)
    await session.commit()
    return repair


def local_factory(session):
    @asynccontextmanager
    async def factory():
        yield session
    return factory


@pytest.mark.asyncio
async def test_hard_budget_blocks_summary_boundary_before_outbound(db_session, monkeypatch):
    await seed(db_session)
    repair = await authorized(db_session, budget=1)
    outbound = AsyncMock(return_value="摘要")
    monkeypatch.setattr(LLMService, "_stream_and_collect", outbound)
    llm = PlatformRepairLLM(db_session, repair_id=repair.id, owner="test-owner")
    llm._repair_session_factory = local_factory(db_session)
    with pytest.raises(RepairBudgetExceeded):
        await llm.get_summary("正文", system_prompt="摘要提示")
    outbound.assert_not_awaited()
    await db_session.refresh(repair)
    assert repair.reserved_tokens == 0


@pytest.mark.asyncio
async def test_budget_caps_output_retries_and_accounts_embeddings(db_session, monkeypatch):
    await seed(db_session)
    repair = await authorized(db_session)
    outbound = AsyncMock(return_value="摘要")
    embeddings = AsyncMock(return_value=[[1.0, 0.0]])
    monkeypatch.setattr(LLMService, "_stream_and_collect", outbound)
    monkeypatch.setattr(LLMService, "get_embeddings_batch", embeddings)
    llm = PlatformRepairLLM(db_session, repair_id=repair.id, owner="test-owner")
    llm._repair_session_factory = local_factory(db_session)
    await llm.get_llm_response("提示", [{"role": "user", "content": "正文"}], max_tokens=99999, max_retries=7, user_id=9901)
    await llm.get_embeddings_batch(["正文"], user_id=9901)
    assert outbound.await_args.kwargs["max_tokens"] == 2048
    assert outbound.await_args.kwargs["max_retries"] == 0
    assert outbound.await_args.kwargs["user_id"] is None
    assert embeddings.await_args.kwargs["user_id"] is None
    await db_session.refresh(repair)
    assert 0 < repair.reserved_tokens <= repair.budget_tokens
    assert repair.used_tokens == repair.reserved_tokens


@pytest.mark.asyncio
async def test_cancel_stops_unstarted_repair_jobs_and_dispatcher_cannot_bypass_budget(db_session):
    await seed(db_session)
    repair = await authorized(db_session, kinds=["summary", "narrative_delta"])
    ids = list(repair.payload["child_job_ids"])
    repair_id = repair.id
    # Other normal adoption jobs can still be dispatched, but no repair child can.
    for _ in range(8):
        claimed = await ChapterDerivationService(db_session).claim_next("ordinary-worker")
        if claimed:
            assert claimed.id not in ids
    await DerivedStateRepairService(db_session).cancel(project_id="repair-project", repair_id=repair_id)
    jobs = (await db_session.execute(select(ChapterDerivationJob).where(ChapterDerivationJob.id.in_(ids)))).scalars().all()
    assert all(job.status == "cancelled" for job in jobs)


@pytest.mark.asyncio
async def test_platform_summary_repair_executes_without_author_credit_charge(db_session, monkeypatch):
    from app.models.credit_log import CreditLog
    await seed(db_session)
    repair = await authorized(db_session)
    monkeypatch.setattr(LLMService, "_stream_and_collect", AsyncMock(return_value="姐姐获救，秦川重新燃起希望。"))
    monkeypatch.setattr("app.services.prompt_service.PromptService.get_prompt", AsyncMock(return_value="抽取摘要"))
    status = await process_repair(db_session, repair.id, "test-owner", session_factory=local_factory(db_session))
    assert status == "completed"
    chapter = (await db_session.execute(select(Chapter))).scalar_one()
    assert chapter.real_summary == "姐姐获救，秦川重新燃起希望。"
    assert (await db_session.execute(select(CreditLog))).scalars().all() == []
    await db_session.refresh(repair)
    assert 0 < repair.reserved_tokens <= repair.budget_tokens


@pytest.mark.asyncio
async def test_narrative_repair_validates_evidence_without_faking_quality_gate(db_session):
    chapter, version, adopted = await seed(db_session)
    repair = await authorized(db_session, kinds=["narrative_delta"])
    job = await db_session.get(ChapterDerivationJob, repair.payload["child_job_ids"][0])
    from app.services.narrative_state_service import NarrativeDelta, NarrativeStateService
    delta = NarrativeDelta(focus="秦川", desire="救姐姐", pressure="失联", payoff="获救", aftereffect="希望",
        next_pull="寻找", emotion="惊喜", facts=[{"entity": "姐姐", "attribute": "生命", "value": "活着",
        "evidence": "姐姐还活着", "confidence": 1}], opened=[], closed=[])
    llm = SimpleNamespace(generate_structured=AsyncMock(return_value=delta))
    await repair_narrative_delta(db_session, job, llm)
    assert "quality_gate" not in version.metadata_
    assert version.metadata_["narrative_delta_repair"]["status"] == "verified"
    state, _ = await NarrativeStateService.load(db_session, chapter.project_id, 2)
    assert state["facts"]


@pytest.mark.asyncio
async def test_repair_worker_reports_exhausted_budget_and_stops_pending_steps(db_session, monkeypatch):
    import asyncio
    import app.services.derived_state_repair_service as module
    await seed(db_session)
    repair = await authorized(db_session, budget=1, kinds=["summary", "state"])
    repair_id, ids = repair.id, repair.payload["child_job_ids"]
    repair.status, repair.lease_owner = "queued", None
    await db_session.commit()
    outbound = AsyncMock(return_value="不应调用")
    monkeypatch.setattr(LLMService, "_stream_and_collect", outbound)
    monkeypatch.setattr("app.services.prompt_service.PromptService.get_prompt", AsyncMock(return_value="摘要"))
    stop = asyncio.Event()
    original = module.process_repair
    async def once(*args, **kwargs):
        try:
            return await original(*args, **kwargs)
        finally:
            stop.set()
    monkeypatch.setattr(module, "process_repair", once)
    await module.run_derived_state_repair_worker(stop, poll_seconds=0.01, session_factory=local_factory(db_session))
    result = await db_session.get(DerivedStateRepair, repair_id)
    await db_session.refresh(result)
    assert result.status == "budget_exhausted"
    outbound.assert_not_awaited()
    children = (await db_session.execute(select(ChapterDerivationJob).where(
        ChapterDerivationJob.id.in_(ids)))).scalars().all()
    assert {job.status for job in children} == {"failed", "cancelled"}


@pytest.mark.asyncio
async def test_repair_worker_recovers_expired_database_lease_without_refunding_reservations(db_session, monkeypatch):
    import asyncio
    import app.services.derived_state_repair_service as module
    await seed(db_session)
    repair = await authorized(db_session)
    repair_id = repair.id
    repair.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    repair.attempts = 1
    repair.reserved_tokens = repair.used_tokens = 10000
    job = await db_session.get(ChapterDerivationJob, repair.payload["child_job_ids"][0])
    job.status, job.lease_owner = "running", "dead-worker"
    job.lease_expires_at = repair.lease_expires_at
    await db_session.commit()
    monkeypatch.setattr(LLMService, "_stream_and_collect", AsyncMock(return_value="姐姐还活着。"))
    monkeypatch.setattr("app.services.prompt_service.PromptService.get_prompt", AsyncMock(return_value="摘要"))
    stop = asyncio.Event()
    original = module.process_repair
    async def once(*args, **kwargs):
        try:
            return await original(*args, **kwargs)
        finally:
            stop.set()
    monkeypatch.setattr(module, "process_repair", once)
    await module.run_derived_state_repair_worker(stop, poll_seconds=0.01, session_factory=local_factory(db_session))
    result = await db_session.get(DerivedStateRepair, repair_id)
    await db_session.refresh(result)
    assert result.status == "completed" and result.attempts == 2
    assert 10000 < result.reserved_tokens <= result.budget_tokens


@pytest.mark.asyncio
async def test_overlapping_platform_repairs_cannot_take_each_others_child_jobs(db_session):
    await seed(db_session)
    first = await authorized(db_session, kinds=["summary"])
    first.status, first.lease_owner = "queued", None
    await db_session.commit()
    service = DerivedStateRepairService(db_session)
    estimate = await service.estimate(project_id="repair-project", admin_user_id=9901,
        chapter_start=1, chapter_end=1, kinds=["summary"])
    with pytest.raises(Exception) as overlap:
        await service.start(project_id="repair-project", repair_id=estimate["id"], admin_user_id=9901,
            estimate_token=estimate["estimate_token"], platform_budget_tokens=200000, confirm_platform_budget=True)
    assert overlap.value.status_code == 409
