"""Version-bound validation shared by derived-memory readers and writers.

Unknown legacy provenance is deliberately not promoted to canon. These helpers
never invoke models and keep external cache results subordinate to SQL truth.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, is_dataclass
from typing import Any

from sqlalchemy import select


def source_payload(source: Any) -> dict:
    if isinstance(source, dict):
        return dict(source)
    if hasattr(source, "model_dump"):
        return source.model_dump(mode="json")
    return asdict(source) if is_dataclass(source) else {}


async def require_current_source(session: Any, source: Any, *, lock: bool = True) -> None:
    if source is None:
        return
    from .chapter_derivation_service import SourceRef, source_is_current

    raw = source_payload(source)
    ref = SourceRef.model_validate({k: v for k, v in raw.items() if k in SourceRef.model_fields})
    if not await source_is_current(session, ref, lock=lock):
        raise ValueError("派生数据来源已变化，拒绝写入旧版本结果")


async def valid_provenance(session: Any, raw: Any, project_id: str, before_chapter: int) -> bool:
    if not isinstance(raw, dict) or raw.get("project_id") != project_id:
        return False
    try:
        number = int(raw.get("chapter_number", raw.get("source_chapter", 0)))
        if not 0 < number < before_chapter:
            return False
        await require_current_source(session, raw, lock=False)
        job_id = raw.get("source_derivation_id")
        if job_id:
            from ..models.chapter_derivation import ChapterDerivationJob
            job = await session.get(ChapterDerivationJob, str(job_id))
            if job is None or job.status != "completed":
                return False
            if any(raw.get(key) != value for key, value in (job.source_ref or {}).items()):
                return False
        return True
    except (ValueError, TypeError, AttributeError):
        return False


async def filter_current_rows(session: Any, rows: list, project_id: str, before_chapter: int) -> list:
    result, checked = [], {}
    for row in rows:
        extra = getattr(row, "extra", None)
        raw = extra.get("provenance") if isinstance(extra, dict) else None
        number = getattr(row, "chapter_number", getattr(row, "cause_chapter", None))
        if (not isinstance(raw, dict) or getattr(row, "project_id", None) != project_id
                or number != raw.get("chapter_number") or not isinstance(number, int)
                or not 0 < number < before_chapter):
            continue
        key = repr(raw)
        if key not in checked:
            checked[key] = await valid_provenance(session, raw, project_id, before_chapter)
        if checked[key]:
            result.append(row)
    return result


async def filter_mem0_results(session: Any, results: list, project_id: str, before_chapter: int) -> list:
    """An external ADD is not visible until its SQL receipt has committed."""
    from ..models.chapter_derivation import ChapterDerivationJob

    ids = {str(r.get("metadata", {}).get("source_derivation_id")) for r in results
           if isinstance(r, dict) and isinstance(r.get("metadata"), dict)
           and r["metadata"].get("source_derivation_id")}
    if not ids:
        return []
    jobs = (await session.execute(select(ChapterDerivationJob).where(
        ChapterDerivationJob.id.in_(ids), ChapterDerivationJob.project_id == project_id,
        ChapterDerivationJob.status == "completed",
    ))).scalars().all()
    receipts = {j.id: j.result or {} for j in jobs}
    valid, checked = [], {}
    for item in results:
        metadata = item.get("metadata") or {}
        if metadata.get("provenance_schema") != 2:
            continue
        job_id = str(metadata.get("source_derivation_id", ""))
        receipt = receipts.get(job_id, {})
        memory_id = str(item.get("id", ""))
        if memory_id not in receipt.get("memory_ids", []):
            continue
        expected = (receipt.get("memory_hashes") or {}).get(memory_id)
        if not expected or hashlib.sha256((item.get("memory") or "").encode()).hexdigest() != expected:
            continue
        key = repr(metadata)
        if key not in checked:
            checked[key] = await valid_provenance(session, metadata, project_id, before_chapter)
        if checked[key]:
            valid.append(item)
    return valid
