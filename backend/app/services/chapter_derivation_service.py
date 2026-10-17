"""Adoption provenance and a database-leased transactional derivation outbox.

Enqueue never commits: the caller commits the adopted manuscript and its work together.
Leases are database compare-and-swap updates, not process-local locks.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, case, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_derivation import ChapterDerivationJob
from ..models.novel import Chapter, ChapterVersion, NovelProject

logger = logging.getLogger(__name__)


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    project_id: str
    chapter_id: int
    chapter_number: int
    source_version_id: int
    source_content_hash: str
    adoption_revision_id: int
    narrative_base: str


class SupersededDerivation(RuntimeError):
    """The adopted text or its preceding canon changed while work was in flight."""


async def narrative_base_for(session: AsyncSession, project_id: str, chapter_number: int, *, lock: bool = False) -> str:
    # This is the same lineage digest as NarrativeStateService.load, without replaying
    # model deltas: malformed historic extraction cannot prevent safe text adoption.
    from .narrative_state_service import digest
    query = (select(Chapter.chapter_number, ChapterVersion.id, ChapterVersion.content)
        .join(ChapterVersion, Chapter.selected_version_id == ChapterVersion.id)
        .where(Chapter.project_id == project_id, Chapter.chapter_number < chapter_number)
        .order_by(Chapter.chapter_number, Chapter.id))
    if lock:
        query = query.with_for_update()
    rows = (await session.execute(query)).all()
    return digest([[number, version_id, hashlib.sha256((text or "").encode()).hexdigest()]
                   for number, version_id, text in rows])


async def build_source_ref(
    session: AsyncSession, *, project_id: str, chapter_number: int, chapter_id: int | None = None,
) -> SourceRef | None:
    query = (select(Chapter, ChapterVersion).join(
        ChapterVersion, Chapter.selected_version_id == ChapterVersion.id,
    ).where(Chapter.project_id == project_id, Chapter.chapter_number == chapter_number)
        .order_by(Chapter.id).execution_options(populate_existing=True))
    if chapter_id is not None:
        query = query.where(Chapter.id == chapter_id)
    row = (await session.execute(query)).first()
    if row is None:
        return None
    chapter, version = row
    return SourceRef(
        project_id=project_id, chapter_id=chapter.id, chapter_number=chapter_number,
        source_version_id=version.id,
        source_content_hash=hashlib.sha256((version.content or "").encode()).hexdigest(),
        adoption_revision_id=int(chapter.revision_id or 0),
        narrative_base=await narrative_base_for(session, project_id, chapter_number),
    )


async def source_is_current(
    session: AsyncSession, source_ref: SourceRef | Mapping[str, Any], *, lock: bool = False,
) -> bool:
    source = SourceRef.model_validate(source_ref)
    base = await narrative_base_for(session, source.project_id, source.chapter_number, lock=lock)
    query = (select(Chapter, ChapterVersion).join(
        ChapterVersion, Chapter.selected_version_id == ChapterVersion.id,
    ).where(Chapter.id == source.chapter_id, Chapter.project_id == source.project_id,
            Chapter.chapter_number == source.chapter_number)
        .execution_options(populate_existing=True))
    if lock:
        # Serialize adoption and materialization on MySQL; SQLite's write transaction
        # plus the conditional update at adoption supplies the equivalent boundary.
        query = query.with_for_update()
    row = (await session.execute(query)).first()
    if not row:
        return False
    chapter, version = row
    return bool(
        version.id == source.source_version_id
        and int(chapter.revision_id or 0) == source.adoption_revision_id
        and hashlib.sha256((version.content or "").encode()).hexdigest() == source.source_content_hash
        and base == source.narrative_base
    )


async def require_current_source(session: AsyncSession, source_ref, *, lock: bool = False) -> None:
    if not await source_is_current(session, source_ref, lock=lock):
        raise SupersededDerivation("adopted source or preceding narrative lineage changed")


async def load_derivation_checkpoint(session: AsyncSession, source_ref, key: str):
    job_id = source_ref.get("source_derivation_id") if isinstance(source_ref, Mapping) else None
    job = await session.get(ChapterDerivationJob, job_id) if job_id else None
    return (job.result or {}).get(key) if job else None


async def save_derivation_checkpoint(session: AsyncSession, source_ref, key: str, payload) -> None:
    job_id = source_ref.get("source_derivation_id") if isinstance(source_ref, Mapping) else None
    if job_id:
        job = await session.get(ChapterDerivationJob, job_id)
        if job:
            job.result = {**(job.result or {}), key: payload}
            await session.commit()


class ChapterDerivationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue_for_adoption(self, source_ref, *, user_id: int, profile: dict | None = None,
                                   only_kinds: list[str] | None = None):
        source = SourceRef.model_validate(source_ref)
        profile = dict(profile or {})
        kinds = ["summary", "index", "volume_summary", "book_summary", "narrative_summary",
                 "character_significance"]
        if profile.get("memory"):
            kinds.append("memory")
        elif profile.get("state"):
            kinds.append("state")
        for key in ("foreshadowing", "outline_revision", "volume_retrospective"):
            if profile.get(key):
                kinds.append(key)
        if only_kinds is not None:
            kinds = list(dict.fromkeys(only_kinds))
        existing = set((await self.session.execute(select(ChapterDerivationJob.kind).where(
            ChapterDerivationJob.chapter_id == source.chapter_id,
            ChapterDerivationJob.adoption_revision_id == source.adoption_revision_id,
        ))).scalars())
        dependencies = {
            "index": ["summary"], "bm25": ["index"], "volume_summary": ["summary"],
            "book_summary": ["volume_summary"], "narrative_summary": ["summary"],
            "outline_revision": ["summary"], "volume_retrospective": ["book_summary"],
        }
        jobs = []
        for kind in kinds:
            if kind in existing:
                continue
            job = ChapterDerivationJob(
                id=str(uuid4()), project_id=source.project_id, chapter_id=source.chapter_id,
                adoption_revision_id=source.adoption_revision_id, kind=kind, status="queued",
                source_ref=source.model_dump(),
                payload={"user_id": user_id, "character_names": profile.get("character_names", []),
                         "depends_on": dependencies.get(kind, [])},
            )
            self.session.add(job)
            jobs.append(job)
        await self.session.flush()
        return jobs

    async def supersede_downstream(self, source_ref) -> None:
        source = SourceRef.model_validate(source_ref)
        # An earlier change also invalidates the lineage carried by every later
        # index, even when that chapter's own text/title hash is unchanged.
        # Clear publication pointers in the same adoption transaction so an
        # incremental rebuild cannot mistake those indexes for already synced.
        await self.session.execute(update(Chapter).where(
            Chapter.project_id == source.project_id, Chapter.chapter_number > source.chapter_number,
        ).values(active_index_revision_id=None, rag_ingest_hash=None)
            .execution_options(synchronize_session=False))
        # Cancel stale queued/in-flight work atomically with adoption. Completed work
        # remains an audit receipt; readers must still validate its source.
        await self.session.execute(update(ChapterDerivationJob).where(
            ChapterDerivationJob.project_id == source.project_id,
            ChapterDerivationJob.status.in_(["queued", "running", "failed"]),
            or_(
                and_(ChapterDerivationJob.chapter_id == source.chapter_id,
                     ChapterDerivationJob.adoption_revision_id != source.adoption_revision_id),
                ChapterDerivationJob.chapter_id.in_(select(Chapter.id).where(
                    Chapter.project_id == source.project_id, Chapter.chapter_number > source.chapter_number)),
            ),
        ).values(status="superseded", lease_owner=None, lease_expires_at=None))

    async def claim_next(self, owner: str, *, lease_seconds: int = 900):
        now = datetime.now(timezone.utc)
        exhausted = await self.session.execute(update(ChapterDerivationJob).where(
            ChapterDerivationJob.status == "running", ChapterDerivationJob.lease_expires_at < now,
            ChapterDerivationJob.attempts >= ChapterDerivationJob.max_attempts,
        ).values(status="failed", lease_owner=None, lease_expires_at=None,
                 last_error="lease_expired_attempts_exhausted").execution_options(synchronize_session=False))
        if exhausted.rowcount:
            await self.session.commit()
        eligible = and_(
            ChapterDerivationJob.payload["repair_id"].as_string().is_(None),
            or_(ChapterDerivationJob.status.in_(["queued", "failed"]),
                and_(ChapterDerivationJob.status == "running", ChapterDerivationJob.lease_expires_at < now)),
            or_(ChapterDerivationJob.next_attempt_at.is_(None), ChapterDerivationJob.next_attempt_at <= now),
            ChapterDerivationJob.attempts < ChapterDerivationJob.max_attempts,
        )
        priority = case(
            (ChapterDerivationJob.kind == "summary", 0),
            (ChapterDerivationJob.kind == "volume_summary", 1),
            (ChapterDerivationJob.kind == "book_summary", 2), else_=3,
        )
        offset, terminal = 0, []
        async def cancel_blocked():
            if terminal:
                await self.session.execute(update(ChapterDerivationJob).where(
                    ChapterDerivationJob.id.in_(terminal),
                    ChapterDerivationJob.status.in_(["queued", "failed"]),
                ).values(status="cancelled", last_error="dependency_terminal_or_missing")
                    .execution_options(synchronize_session=False))
        while True:
            jobs = (await self.session.execute(select(ChapterDerivationJob).where(eligible)
                    .order_by(priority, ChapterDerivationJob.created_at, ChapterDerivationJob.id)
                    .offset(offset).limit(200))).scalars().all()
            for job in jobs:
                if (job.payload or {}).get("repair_id"):
                    continue
                deps = (job.payload or {}).get("depends_on", [])
                if deps:
                    dependencies = (await self.session.execute(select(ChapterDerivationJob).where(
                        ChapterDerivationJob.chapter_id == job.chapter_id,
                        ChapterDerivationJob.adoption_revision_id == job.adoption_revision_id,
                        ChapterDerivationJob.kind.in_(deps),
                    ))).scalars().all()
                    if len(dependencies) != len(deps) or any(
                        dep.status in {"cancelled", "superseded"} or (
                            dep.status == "failed" and dep.attempts >= dep.max_attempts)
                        for dep in dependencies
                    ):
                        terminal.append(job.id)
                        continue
                    if any(dep.status != "completed" for dep in dependencies):
                        continue
                claimed = await self.session.execute(update(ChapterDerivationJob).where(
                    ChapterDerivationJob.id == job.id, eligible,
                ).values(status="running", lease_owner=owner,
                         lease_expires_at=now + timedelta(seconds=lease_seconds),
                         attempts=ChapterDerivationJob.attempts + 1)
                    .execution_options(synchronize_session=False))
                if claimed.rowcount == 1:
                    await cancel_blocked()
                    await self.session.commit()
                    await self.session.refresh(job)
                    return job
            offset += len(jobs)
            if len(jobs) < 200:
                break
        if terminal:
            await cancel_blocked()
            await self.session.commit()
        else:
            await self.session.rollback()
        return None

    async def finish(self, job_id: str, owner: str, *, status: str, result=None, error: str | None = None):
        now = datetime.now(timezone.utc)
        values = dict(status=status, last_error=(error or "")[:2000] or None,
                      lease_owner=None, lease_expires_at=None,
                      next_attempt_at=now + timedelta(seconds=30) if status == "failed" else None)
        if result is not None:
            checkpoint = (await self.session.execute(select(ChapterDerivationJob.result).where(
                ChapterDerivationJob.id == job_id,
            ))).scalar_one_or_none() or {}
            values["result"] = {**checkpoint, **result}
        await self.session.execute(update(ChapterDerivationJob).where(
            ChapterDerivationJob.id == job_id, ChapterDerivationJob.status == "running",
            ChapterDerivationJob.lease_owner == owner,
        ).values(**values))
        await self.session.commit()


async def execute_derivation_job(session: AsyncSession, job: ChapterDerivationJob, *, llm_service=None) -> dict:
    """Reuse the existing calls; never expand an unrequested extraction profile."""
    from .chapter_post_processor import ChapterPostProcessor
    from .llm_service import LLMService
    from .prompt_service import PromptService

    source = SourceRef.model_validate(job.source_ref)
    await require_current_source(session, source)
    version = await session.get(ChapterVersion, source.source_version_id)
    text = version.content
    user_id = int(job.payload["user_id"])
    processor = ChapterPostProcessor(session, llm_service or LLMService(session))
    ref = {**source.model_dump(), "source_derivation_id": job.id}
    common = dict(project_id=source.project_id, chapter_number=source.chapter_number, user_id=user_id)
    if job.kind == "summary":
        result = {"summary": await processor._ensure_summary(
            source.project_id, source.chapter_number, text, user_id, source_ref=source, derivation_job_id=job.id)}
        if not result["summary"]:
            raise RuntimeError("summary generation returned no usable summary")
    elif job.kind == "index":
        result = await processor._ingest_and_hash(source.project_id, source.chapter_number, text, user_id,
                                                   source_ref=source, strict=True)
        if result.get("bm25_status") == "degraded" and not job.payload.get("repair_id"):
            await ChapterDerivationService(session).enqueue_for_adoption(
                source, user_id=user_id, only_kinds=["bm25"])
            await session.commit()
    elif job.kind == "bm25":
        from .retrieval_scope import build_retrieval_scope
        from .vector_store_service import VectorStoreService
        scope = await build_retrieval_scope(project_id=source.project_id,
            before_chapter=source.chapter_number + 1, session=session)
        receipt = await VectorStoreService().sync_bm25_revision(scope=scope, chapter_number=source.chapter_number)
        result = {"applied": True, "bm25_status": "synced", "count": receipt.written}
    elif job.kind in {"volume_summary", "book_summary", "narrative_summary"}:
        if job.kind == "volume_summary":
            outcome = await processor._update_volume_summary(source.project_id, source.chapter_number, user_id, strict=True)
        elif job.kind == "book_summary":
            outcome = await processor._update_book_summary(source.project_id, user_id, strict=True)
        else:
            outcome = await processor._update_narrative_summary(source.project_id, source.chapter_number, user_id, strict=True)
        result = outcome if isinstance(outcome, dict) else ({"applied": True} if outcome else {
            "applied": False, "skipped": "not_ready_or_model_unavailable"})
    elif job.kind == "character_significance":
        result = await processor._update_character_significance(
            source.project_id, source.chapter_number, text, user_id, source_ref=ref)
    elif job.kind in {"memory", "state"}:
        from .memory_layer_service import MemoryLayerService
        memory = MemoryLayerService(session, processor._llm, PromptService(session))
        operation = memory.update_memory_after_chapter if job.kind == "memory" else memory.update_state_after_chapter
        result = await operation(**common, chapter_content=text,
                                 character_names=job.payload.get("character_names", []), source_ref=ref)
    elif job.kind == "foreshadowing":
        from .foreshadowing_service import ForeshadowingService
        result = await ForeshadowingService(session, source_ref=ref).extract_foreshadowings_from_chapter(
            **common, chapter_id=source.chapter_id, chapter_content=text,
            llm_service=processor._llm, prompt_service=PromptService(session))
    elif job.kind == "outline_revision":
        from .outline_revision_service import OutlineRevisionService
        result = await OutlineRevisionService().review_downstream(
            project_id=source.project_id, finalized_chapter_number=source.chapter_number,
            chapter_content=text, session=session, llm_service=processor._llm,
            prompt_service=PromptService(session), user_id=user_id, source_ref=ref)
    elif job.kind == "volume_retrospective":
        from .volume_retrospective_service import VolumeRetrospectiveService
        result = await VolumeRetrospectiveService().review_volume(
            project_id=source.project_id, finalized_chapter_number=source.chapter_number,
            session=session, llm_service=processor._llm, prompt_service=PromptService(session),
            user_id=user_id, source_ref=ref)
    else:
        raise ValueError(f"unknown derivation kind: {job.kind}")
    await require_current_source(session, source)
    if isinstance(result, dict) and (result.get("skipped") in {"llm_failed", "no_result"}
                                    or str(result.get("skipped", "")).startswith("error:")):
        raise RuntimeError(f"Derivation did not produce a usable result: {result['skipped']}")
    return result if isinstance(result, dict) else {"applied": bool(result)}


async def run_derivation_worker(stop_event: asyncio.Event, *, poll_seconds: float = 2,
                                session_factory=None) -> None:
    """Restart recovery is automatic: expired database leases are reclaimable."""
    if session_factory is None:
        from ..db.session import AsyncSessionLocal
        session_factory = AsyncSessionLocal
    owner = str(uuid4())
    while not stop_event.is_set():
        claimed = False
        try:
            async with session_factory() as session:
                service = ChapterDerivationService(session)
                job = await service.claim_next(owner)
                if job:
                    claimed = True
                    job_id = job.id
                    try:
                        # Keep the lease long enough for slow multi-provider extraction,
                        # while bounding every attempt below that lease.
                        result = await asyncio.wait_for(execute_derivation_job(session, job), timeout=840)
                        await service.finish(job_id, owner, status="completed", result=result)
                    except SupersededDerivation as exc:
                        await session.rollback()
                        await service.finish(job_id, owner, status="superseded", error=str(exc))
                    except asyncio.CancelledError:
                        await session.rollback()
                        raise
                    except Exception as exc:
                        await session.rollback()
                        logger.exception("Chapter derivation failed id=%s", job_id)
                        await service.finish(job_id, owner, status="failed", error=type(exc).__name__)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Chapter derivation dispatcher failed")
        if not claimed:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass
