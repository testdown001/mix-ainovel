"""Explicit platform repair: immutable estimates, SQL leases and hard call budgets.

Budget units are conservative token upper bounds, not a currency quotation. Every
outbound call reserves its full upper bound durably before it starts. Reservations
are never refunded after uncertain transport failure or a process crash.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update

from ..models.derived_state_repair import DerivedStateRepair
from ..models.chapter_derivation import ChapterDerivationJob
from ..models.novel import Chapter, ChapterVersion, NovelProject
from .chapter_derivation_service import (
    SourceRef, SupersededDerivation, build_source_ref, execute_derivation_job,
    require_current_source, source_is_current,
)
from .llm_service import LLMService

logger = logging.getLogger(__name__)
ALLOWED_KINDS = {"summary", "index", "state", "narrative_delta"}
OUTPUT_CAP = 2048


class RepairBudgetExceeded(RuntimeError):
    pass


class RepairCancelled(RuntimeError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class PlatformRepairLLM(LLMService):
    """Guard the shared low-level boundary, including summary and fallback calls."""
    def __init__(self, session, *, repair_id: str, owner: str):
        super().__init__(session)
        self.repair_id = repair_id
        self.owner = owner
        self.budget_blocked = False

    async def _reserve(self, tokens: int):
        # Use a separate short transaction: model helpers commit their own SQL,
        # and a late failure must not roll back an already spent reservation.
        from ..db.session import AsyncSessionLocal
        factory = getattr(self, "_repair_session_factory", AsyncSessionLocal)
        async with factory() as budget_session:
            amount = max(1, int(tokens))
            changed = await budget_session.execute(update(DerivedStateRepair).where(
                DerivedStateRepair.id == self.repair_id,
                DerivedStateRepair.status == "running", DerivedStateRepair.lease_owner == self.owner,
                DerivedStateRepair.reserved_tokens + amount <= DerivedStateRepair.budget_tokens,
            ).values(reserved_tokens=DerivedStateRepair.reserved_tokens + amount,
                     used_tokens=DerivedStateRepair.used_tokens + amount,
                     lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=900))
                .execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                row = await budget_session.get(DerivedStateRepair, self.repair_id)
                status = row.status if row else None
                await budget_session.rollback()
                self.budget_blocked = True
                if status is None or status in {"cancel_requested", "cancelled"}:
                    raise RepairCancelled("repair cancelled before next model call")
                raise RepairBudgetExceeded("platform token budget exhausted or lease lost")
            await budget_session.commit()

    async def _stream_and_collect(self, messages, **kwargs):
        cap = min(int(kwargs.get("max_tokens") or OUTPUT_CAP), OUTPUT_CAP)
        # UTF-8 bytes bound tokenized input; protocol/schema headroom plus a
        # factor of three conservatively covers SDK-level transport retries.
        serialized = json.dumps(messages, ensure_ascii=False).encode()
        await self._reserve(3 * (len(serialized) + 4096 + cap))
        kwargs.update(max_tokens=cap, max_retries=0, user_id=None,
                      disable_thinking=True, thinking_budget=0)
        kwargs.setdefault("temperature", 0.2)
        kwargs["timeout"] = min(float(kwargs.get("timeout") or 120), 120)
        return await super()._stream_and_collect(messages, **kwargs)

    async def get_llm_response(self, *args, **kwargs):
        kwargs.update(user_id=None, max_retries=0)
        return await super().get_llm_response(*args, **kwargs)

    async def generate_structured(self, **kwargs):
        if kwargs.get("responder") is not None:
            raise ValueError("repair cannot use an unbudgeted responder")
        kwargs.update(max_validation_retries=0, request_max_retries=0, user_id=None,
                      max_tokens=min(int(kwargs.get("max_tokens") or OUTPUT_CAP), OUTPUT_CAP))
        return await super().generate_structured(**kwargs)

    async def get_embeddings_batch(self, texts, **kwargs):
        await self._reserve(3 * (sum(len(text.encode()) for text in texts) + 4096))
        kwargs["user_id"] = None
        return await super().get_embeddings_batch(texts, **kwargs)

    async def get_embedding(self, text, **kwargs):
        await self._reserve(3 * (len(text.encode()) + 4096))
        kwargs["user_id"] = None
        return await super().get_embedding(text, **kwargs)

    async def chat_with_tools(self, *args, **kwargs):
        raise ValueError("tool calls are outside the authorized repair profile")


class DerivedStateRepairService:
    def __init__(self, session):
        self.session = session

    async def _project(self, project_id):
        project = await self.session.get(NovelProject, project_id)
        if project is None:
            raise HTTPException(404, "项目不存在")
        return project

    async def _manifest(self, project_id, start, end):
        refs = []
        for number in range(start, end + 1):
            ref = await build_source_ref(self.session, project_id=project_id, chapter_number=number)
            if ref is not None:
                refs.append(ref.model_dump())
        return refs

    async def estimate(self, *, project_id, admin_user_id, chapter_start, chapter_end, kinds):
        await self._project(project_id)
        if not 1 <= chapter_start <= chapter_end or chapter_end - chapter_start >= 100:
            raise HTTPException(422, "每批修复须为 1–100 章的有效范围")
        kinds = list(dict.fromkeys(kinds))
        if not kinds or set(kinds) - ALLOWED_KINDS:
            raise HTTPException(422, "不支持的派生修复类型")
        manifest = await self._manifest(project_id, chapter_start, chapter_end)
        if not manifest:
            raise HTTPException(400, "指定范围没有作者采用的正文")
        upper = 0
        for ref in manifest:
            version = await self.session.get(ChapterVersion, ref["source_version_id"])
            size = len(version.content.encode())
            for kind in kinds:
                # State extraction currently has up to two calls. Actual runtime
                # reservation is authoritative if prompts/configuration grow.
                calls = 2 if kind == "state" else 1
                upper += calls * 3 * (size + 32768 + (0 if kind == "index" else OUTPUT_CAP))
        payload = {"chapter_start": chapter_start, "chapter_end": chapter_end, "kinds": kinds,
                   "manifest": manifest, "estimated_upper_tokens": upper,
                   "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}
        repair = DerivedStateRepair(
            id=str(uuid4()), project_id=project_id, admin_user_id=admin_user_id,
            status="estimated", estimate_token=secrets.token_hex(32),
            source_fingerprint=_digest({"manifest": manifest, "kinds": kinds}), payload=payload,
        )
        self.session.add(repair)
        await self.session.commit()
        return self.serialize(repair)

    async def _get(self, project_id, repair_id, *, lock=False):
        await self._project(project_id)
        query = select(DerivedStateRepair).where(
            DerivedStateRepair.id == repair_id, DerivedStateRepair.project_id == project_id,
        ).execution_options(populate_existing=True)
        if lock:
            query = query.with_for_update()
        row = (await self.session.execute(query)).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "修复任务不存在")
        return row

    async def validate_manifest(self, repair):
        payload = repair.payload
        current = await self._manifest(repair.project_id, payload["chapter_start"], payload["chapter_end"])
        if _digest({"manifest": current, "kinds": payload["kinds"]}) != repair.source_fingerprint:
            raise SupersededDerivation("repair estimate source fingerprint changed")

    async def _artifact_current(self, job, source):
        if job.status != "completed" or job.source_ref != source:
            return False
        chapter = await self.session.get(Chapter, source["chapter_id"])
        if job.kind == "index":
            return bool(chapter.active_index_revision_id and chapter.rag_ingest_hash and
                        (job.result or {}).get("index_revision_id") == chapter.active_index_revision_id)
        if job.kind == "summary":
            from ..models.project_memory import ProjectMemory
            memory = (await self.session.execute(select(ProjectMemory).where(
                ProjectMemory.project_id == source["project_id"]))).scalar_one_or_none()
            marker = ((memory.extra or {}).get("chapter_summary_sources", {}).get(str(source["chapter_number"]), {})
                      if memory else {})
            return bool(chapter.real_summary and marker.get("source_ref") == source and marker.get("summary_hash") ==
                        hashlib.sha256(chapter.real_summary.encode()).hexdigest())
        if job.kind == "narrative_delta":
            version = await self.session.get(ChapterVersion, source["source_version_id"])
            marker = (version.metadata_ or {}).get("narrative_delta_repair", {})
            return bool(marker.get("status") == "verified" and marker.get("content_hash") == source["source_content_hash"]
                        and marker.get("narrative_base") == source["narrative_base"])
        # An empty extraction can be a valid result, but requires the recorded
        # extraction checkpoints rather than a generic completed flag.
        return any(key.startswith("extraction_") for key in (job.result or {}))

    async def start(self, *, project_id, repair_id, admin_user_id, estimate_token,
                    platform_budget_tokens, confirm_platform_budget):
        repair = await self._get(project_id, repair_id, lock=True)
        if repair.admin_user_id != admin_user_id or not secrets.compare_digest(repair.estimate_token, estimate_token):
            raise HTTPException(403, "估算凭证无效或不属于当前管理员")
        if repair.status != "estimated":
            return self.serialize(repair)  # lost-response retry does not spend twice
        if not confirm_platform_budget or platform_budget_tokens <= 0:
            raise HTTPException(428, "必须明确授权平台预算；不会扣除作者积分")
        if datetime.fromisoformat(repair.payload["expires_at"]) < datetime.now(timezone.utc):
            raise HTTPException(409, "估算已过期，请重新估算")
        try:
            await self.validate_manifest(repair)
        except SupersededDerivation as exc:
            raise HTTPException(409, "正文或正史谱系已变化，请重新估算") from exc
        jobs = []
        from ..models.novel import BlueprintCharacter
        names = (await self.session.execute(select(BlueprintCharacter.name).where(
            BlueprintCharacter.project_id == project_id))).scalars().all()
        for source in repair.payload["manifest"]:
            version = await self.session.get(ChapterVersion, source["source_version_id"])
            for kind in repair.payload["kinds"]:
                existing = (await self.session.execute(select(ChapterDerivationJob).where(
                    ChapterDerivationJob.chapter_id == source["chapter_id"],
                    ChapterDerivationJob.adoption_revision_id == source["adoption_revision_id"],
                    ChapterDerivationJob.kind == kind,
                ).with_for_update())).scalar_one_or_none()
                if existing and existing.status == "running":
                    raise HTTPException(409, "对应派生任务正在执行，请稍后重新估算")
                previous_repair_id = (existing.payload or {}).get("repair_id") if existing else None
                if previous_repair_id and previous_repair_id != repair.id:
                    previous_repair = await self.session.get(DerivedStateRepair, previous_repair_id)
                    if previous_repair and previous_repair.status in {"queued", "running", "cancel_requested"}:
                        raise HTTPException(409, "相同派生步骤已属于另一项进行中的平台修复")
                if existing and await self._artifact_current(existing, source):
                    jobs.append(existing.id)
                    continue
                if existing is None:
                    existing = ChapterDerivationJob(
                        id=str(uuid4()), project_id=project_id, chapter_id=source["chapter_id"],
                        adoption_revision_id=source["adoption_revision_id"], kind=kind,
                    )
                    self.session.add(existing)
                same_source = existing.source_ref == source if existing.source_ref else False
                existing.source_ref = source
                existing.payload = {"repair_id": repair.id, "user_id": admin_user_id,
                                    "character_names": [name for name in names if name in version.content][:16],
                                    "depends_on": []}
                if not same_source:
                    existing.result = None
                existing.status = "queued"
                existing.attempts = 0
                existing.lease_owner = None
                existing.lease_expires_at = None
                existing.next_attempt_at = None
                jobs.append(existing.id)
        repair.payload = {**repair.payload, "child_job_ids": jobs}
        repair.budget_tokens = int(platform_budget_tokens)
        repair.status = "queued"
        await self.session.commit()
        return self.serialize(repair)

    async def status(self, *, project_id, repair_id):
        row = await self._get(project_id, repair_id)
        response = self.serialize(row)
        ids = row.payload.get("child_job_ids", [])
        if ids:
            jobs = (await self.session.execute(select(ChapterDerivationJob).where(
                ChapterDerivationJob.id.in_(ids)))).scalars().all()
            response["steps"] = [{"id": job.id, "chapter_number": job.source_ref["chapter_number"],
                                  "kind": job.kind, "status": job.status, "result": job.result,
                                  "last_error": job.last_error} for job in jobs]
        return response

    async def cancel(self, *, project_id, repair_id):
        repair = await self._get(project_id, repair_id, lock=True)
        if repair.status in {"estimated", "queued", "running"}:
            repair.status = "cancel_requested" if repair.status == "running" else "cancelled"
            ids = repair.payload.get("child_job_ids", [])
            for job in (await self.session.execute(select(ChapterDerivationJob).where(
                ChapterDerivationJob.id.in_(ids), ChapterDerivationJob.status.in_(["queued", "failed"]),
            ))).scalars():
                if (job.payload or {}).get("repair_id") == repair.id:
                    job.status = "cancelled"
            await self.session.commit()
        return self.serialize(repair)

    @staticmethod
    def serialize(row):
        return {"id": row.id, "project_id": row.project_id, "status": row.status,
                "estimate_token": row.estimate_token, "source_fingerprint": row.source_fingerprint,
                "chapter_start": row.payload["chapter_start"], "chapter_end": row.payload["chapter_end"],
                "kinds": row.payload["kinds"], "estimated_upper_tokens": row.payload["estimated_upper_tokens"],
                "expires_at": row.payload["expires_at"],
                "budget_tokens": row.budget_tokens, "reserved_tokens": row.reserved_tokens,
                "used_tokens": row.used_tokens, "result": row.result, "error": row.error,
                "billing": "platform_only", "estimate_note": "保守 token 上限，非精确费用；调用前按实际输入硬预留预算"}


async def repair_narrative_delta(session, job, llm):
    from .narrative_state_service import NarrativeDelta, NarrativeStateService
    from .chapter_derivation_service import load_derivation_checkpoint, save_derivation_checkpoint
    source = SourceRef.model_validate(job.source_ref)
    ref = {**source.model_dump(), "source_derivation_id": job.id}
    await require_current_source(session, source)
    version = await session.get(ChapterVersion, source.source_version_id)
    state, base = await NarrativeStateService.load(session, source.project_id, source.chapter_number)
    cached = await load_derivation_checkpoint(session, ref, "extraction_narrative_delta")
    delta = NarrativeDelta.model_validate(cached) if cached is not None else await llm.generate_structured(
        prompt=f"[既有正史]\n{json.dumps(state, ensure_ascii=False)}\n[已采用正文]\n{version.content}",
        schema=NarrativeDelta, system_prompt="只抽取正文实际发生的事实与读者承诺变化，证据必须逐字摘自正文；不把计划写成事实。",
        temperature=0.1, max_tokens=OUTPUT_CAP, max_validation_retries=0, request_max_retries=0,
    )
    await save_derivation_checkpoint(session, ref, "extraction_narrative_delta", delta.model_dump())
    NarrativeStateService.validate_evidence(delta, version.content, state)
    await require_current_source(session, source, lock=True)
    meta = dict(version.metadata_ or {})
    meta["narrative_delta_repair"] = {"status": "verified", "content_hash": source.source_content_hash,
        "narrative_base": base, "narrative_delta": delta.model_dump(), "source_ref": ref}
    # Preserve the original prose quality verdict; extraction is not a new quality score.
    version.metadata_ = meta
    await session.commit()
    return {"applied": True, "coverage": "verified", "facts": len(delta.facts)}


async def process_repair(session, repair_id, owner, *, session_factory=None):
    service = DerivedStateRepairService(session)
    repair = await session.get(DerivedStateRepair, repair_id)
    llm = PlatformRepairLLM(session, repair_id=repair_id, owner=owner)
    if session_factory:
        llm._repair_session_factory = session_factory
    # Chapter order matters: each explicit delta repair may inform the next delta.
    jobs = (await session.execute(select(ChapterDerivationJob).where(
        ChapterDerivationJob.id.in_(repair.payload["child_job_ids"]),
    ))).scalars().all()
    order = {"summary": 0, "index": 1, "state": 2, "narrative_delta": 3}
    jobs.sort(key=lambda job: (job.source_ref["chapter_number"], order[job.kind]))
    for job in jobs:
        await session.refresh(repair)
        if repair.status in {"cancel_requested", "cancelled"}:
            return "cancelled"
        if repair.status != "running" or repair.lease_owner != owner:
            raise RepairCancelled("repair lease ownership changed")
        await service.validate_manifest(repair)
        if job.status == "completed":
            continue
        if job.status in {"cancelled", "superseded"}:
            raise SupersededDerivation("repair step superseded or cancelled")
        if (job.payload or {}).get("repair_id") != repair_id:
            raise SupersededDerivation("repair step ownership changed")
        job.status, job.lease_owner = "running", owner
        job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=900)
        job.attempts = int(job.attempts or 0) + 1
        repair.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=900)
        await session.commit()
        job_id = job.id
        try:
            operation = repair_narrative_delta(session, job, llm) if job.kind == "narrative_delta" else (
                execute_derivation_job(session, job, llm_service=llm))
            result = await asyncio.wait_for(operation, timeout=840)
            if llm.budget_blocked:
                raise RepairBudgetExceeded("platform token budget exhausted")
            await service.validate_manifest(repair)
            await session.refresh(job)
            receipt = {**(job.result or {}), **result}
            published = await session.execute(update(ChapterDerivationJob).where(
                ChapterDerivationJob.id == job_id, ChapterDerivationJob.status == "running",
                ChapterDerivationJob.lease_owner == owner,
            ).values(status="completed", lease_owner=None, lease_expires_at=None, result=receipt)
                .execution_options(synchronize_session=False))
            if published.rowcount != 1:
                raise RepairCancelled("repair step lease lost before receipt publication")
            await session.refresh(repair)
            recorded = dict((repair.result or {}).get("steps", {}))
            recorded[job.id] = {"kind": job.kind, "chapter_number": job.source_ref["chapter_number"],
                                "status": "completed", "result": receipt}
            repair.result = {**(repair.result or {}), "steps": recorded}
            await session.commit()
        except BaseException:
            await session.rollback()
            await session.execute(update(ChapterDerivationJob).where(
                ChapterDerivationJob.id == job_id, ChapterDerivationJob.lease_owner == owner,
            ).values(status="failed", lease_owner=None, lease_expires_at=None)
                .execution_options(synchronize_session=False))
            await session.commit()
            raise
    await session.refresh(repair)
    return "cancelled" if repair.status in {"cancel_requested", "cancelled"} else "completed"


async def run_derived_state_repair_worker(stop_event: asyncio.Event, *, poll_seconds=3, session_factory=None):
    if session_factory is None:
        from ..db.session import AsyncSessionLocal
        session_factory = AsyncSessionLocal
    owner = str(uuid4())
    while not stop_event.is_set():
        claimed = False
        try:
            async with session_factory() as session:
                now = datetime.now(timezone.utc)
                exhausted_ids = (await session.execute(select(DerivedStateRepair.id).where(
                    DerivedStateRepair.status == "running", DerivedStateRepair.lease_expires_at < now,
                    DerivedStateRepair.attempts >= 3,
                ))).scalars().all()
                await session.execute(update(DerivedStateRepair).where(
                    DerivedStateRepair.status == "running", DerivedStateRepair.lease_expires_at < now,
                    DerivedStateRepair.attempts >= 3,
                ).values(status="failed", lease_owner=None, lease_expires_at=None,
                         error="lease_expired_attempts_exhausted").execution_options(synchronize_session=False))
                if exhausted_ids:
                    await session.execute(update(ChapterDerivationJob).where(
                        ChapterDerivationJob.payload["repair_id"].as_string().in_(exhausted_ids),
                        ChapterDerivationJob.status.in_(["queued", "running"]),
                    ).values(status="failed", lease_owner=None, lease_expires_at=None,
                             last_error="repair_lease_expired_attempts_exhausted")
                        .execution_options(synchronize_session=False))
                await session.commit()
                eligible = or_(DerivedStateRepair.status == "queued", and_(
                    DerivedStateRepair.status == "running", DerivedStateRepair.lease_expires_at < now,
                ))
                ids = (await session.execute(select(DerivedStateRepair.id).where(
                    eligible, DerivedStateRepair.attempts < 3,
                ).order_by(DerivedStateRepair.created_at).limit(20))).scalars().all()
                for repair_id in ids:
                    changed = await session.execute(update(DerivedStateRepair).where(
                        DerivedStateRepair.id == repair_id, eligible,
                    ).values(status="running", lease_owner=owner,
                             lease_expires_at=now + timedelta(seconds=900),
                             attempts=DerivedStateRepair.attempts + 1)
                        .execution_options(synchronize_session=False))
                    await session.commit()
                    if changed.rowcount != 1:
                        continue
                    claimed = True
                    error = None
                    try:
                        status = await process_repair(session, repair_id, owner, session_factory=session_factory)
                    except RepairCancelled:
                        status = "cancelled"
                    except RepairBudgetExceeded:
                        status, error = "budget_exhausted", "平台预算已耗尽；未开始的步骤未执行"
                    except SupersededDerivation:
                        status, error = "stale", "正文或正史谱系已变化，请重新估算"
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.exception("Platform repair failed id=%s", repair_id)
                        status, error = "failed", type(exc).__name__
                    await session.rollback()
                    repair_row = await session.get(DerivedStateRepair, repair_id)
                    if status != "completed":
                        ids_to_stop = repair_row.payload.get("child_job_ids", [])
                        await session.execute(update(ChapterDerivationJob).where(
                            ChapterDerivationJob.id.in_(ids_to_stop),
                            ChapterDerivationJob.payload["repair_id"].as_string() == repair_id,
                            ChapterDerivationJob.status == "queued",
                        ).values(status="cancelled", last_error=f"repair_{status}")
                            .execution_options(synchronize_session=False))
                    await session.execute(update(DerivedStateRepair).where(
                        DerivedStateRepair.id == repair_id, DerivedStateRepair.lease_owner == owner,
                    ).values(status=status, error=error, lease_owner=None, lease_expires_at=None)
                        .execution_options(synchronize_session=False))
                    await session.commit()
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Platform repair dispatcher failed")
        if not claimed:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass
