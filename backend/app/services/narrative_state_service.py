"""Version-bound story facts and reader promises. Drafts never mutate canonical memory."""
from __future__ import annotations

import hashlib
from collections import Counter
import json
import re
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select


class StoryFact(BaseModel):
    entity: str = Field(min_length=1, max_length=80)
    attribute: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=300)
    evidence: str = Field(min_length=1, max_length=300)
    supersedes_value: str | None = None
    valid_until_chapter: int | None = None
    confidence: float = Field(ge=0, le=1)
    related_entities: list[str] = Field(default_factory=list, max_length=8)


class ReaderPromise(BaseModel):
    question: str = Field(min_length=1, max_length=240)
    character: str = Field(max_length=80)
    expected_payoff_chapter: int | None = None
    evidence: str = Field(min_length=1, max_length=300)


class PromiseResolution(BaseModel):
    promise_id: str
    evidence: str = Field(min_length=1, max_length=300)
    change: str = Field(min_length=1, max_length=300)


class NarrativeDelta(BaseModel):
    focus: str = Field(max_length=160)
    desire: str = Field(max_length=240)
    pressure: str = Field(max_length=240)
    payoff: str = Field(max_length=240)
    aftereffect: str = Field(max_length=240)
    next_pull: str = Field(max_length=240)
    emotion: str = Field(max_length=160)
    facts: list[StoryFact] = Field(max_length=20)
    opened: list[ReaderPromise] = Field(max_length=6)
    closed: list[PromiseResolution] = Field(max_length=6)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def terms(text: str) -> set[str]:
    """Chinese bigrams plus words, without an extra embedding call on the critical path."""
    words = set(re.findall(r"[a-z0-9_]+", text.lower()))
    for part in re.findall(r"[\u4e00-\u9fff]+", text):
        words.update(part[i:i + 2] for i in range(max(1, len(part) - 1)))
    return words


def relevance(query: str, text: str) -> float:
    needles = terms(query)
    return len(needles & terms(text)) / max(1, len(needles))


class NarrativeStateService:
    @staticmethod
    def empty() -> dict:
        return {"facts": {}, "conflicts": {}, "promises": {}, "reader": {}, "history": []}

    @staticmethod
    def validate_evidence(delta: NarrativeDelta, text: str, state: dict) -> None:
        """No invented citations and no closure of an unknown promise."""
        compact = "".join(text.split())
        for item in [*delta.facts, *delta.opened, *delta.closed]:
            if not "".join(item.evidence.split()) or "".join(item.evidence.split()) not in compact:
                raise ValueError("叙事状态证据不在正文中")
        for item in delta.closed:
            if item.promise_id not in state.get("promises", {}):
                raise ValueError("不能兑现未登记的读者承诺")

    @staticmethod
    def apply(state: dict, delta: dict, *, chapter: int, version_id: int | None = None) -> dict:
        result = json.loads(json.dumps(state, ensure_ascii=False))
        for fact in delta.get("facts", []):
            key = digest([fact["entity"].strip(), fact["attribute"].strip()])[:24]
            incoming = {**fact, "source_chapter": chapter, "source_version": version_id,
                        "valid_from_chapter": chapter}
            previous = result["facts"].get(key)
            if previous and previous["value"] != fact["value"]:
                expired = previous.get("valid_until_chapter")
                if fact.get("supersedes_value") == previous["value"] or (expired is not None and expired < chapter):
                    incoming["supersedes"] = {"value": previous["value"], "source_version": previous.get("source_version")}
                    result["conflicts"].pop(key, None)
                else:
                    result["conflicts"][key] = [previous, incoming]
                    # Keep neither conflicting value in the injected canon.
                    result["facts"].pop(key, None)
                    continue
            elif key in result["conflicts"]:
                alternatives = result["conflicts"][key]
                if not fact.get("supersedes_value") or fact["supersedes_value"] not in {f["value"] for f in alternatives}:
                    result["conflicts"][key] = (alternatives + [incoming])[-4:]
                    continue
                result["conflicts"].pop(key)
            result["facts"][key] = incoming
        for promise in delta.get("opened", []):
            key = digest([promise["character"], promise["question"]])[:24]
            if key not in result["promises"]:
                result["promises"][key] = {**promise, "id": key, "status": "open",
                                           "source_chapter": chapter, "source_version": version_id}
        for closure in delta.get("closed", []):
            if closure["promise_id"] in result["promises"]:
                result["promises"][closure["promise_id"]].update(
                    status="closed", resolved_chapter=chapter, resolution=closure)
        result["reader"] = {k: v for k, v in delta.items() if k not in {"facts", "opened", "closed"}}
        result["history"] = (result["history"] + [result["reader"]])[-6:]
        return result

    @staticmethod
    def for_scene(state: dict, scene: dict, chapter: int, limit: int = 12) -> dict:
        query = json.dumps(scene, ensure_ascii=False)
        facts = [f for f in state.get("facts", {}).values()
                 if f["valid_from_chapter"] <= chapter
                 and (f.get("valid_until_chapter") is None or chapter <= f["valid_until_chapter"])]
        facts.sort(key=lambda f: (relevance(query, json.dumps(f, ensure_ascii=False)), f["confidence"]), reverse=True)
        promises = [p for p in state.get("promises", {}).values() if p["status"] == "open"]
        promises.sort(key=lambda p: (p.get("expected_payoff_chapter") is not None
                                      and p["expected_payoff_chapter"] <= chapter,
                                      relevance(query, json.dumps(p, ensure_ascii=False))), reverse=True)
        return {"facts": facts[:limit], "open_promises": promises[:12], "reader": state.get("reader", {}),
                "recent_changes": state.get("history", [])[-4:],
                "unresolved_conflicts": [{"entity": values[-1]["entity"], "attribute": values[-1]["attribute"],
                                           "instruction": "存在未裁决冲突，不得将任一候选值当作确定事实"}
                                          for values in state.get("conflicts", {}).values()][:12]}

    @classmethod
    async def _replay(cls, session, project_id: str, chapter_number: int) -> tuple[dict, str, dict]:
        """Replay only selected, evidenced versions; missing or malformed history is explicit."""
        from ..models.novel import Chapter, ChapterVersion
        rows = (await session.execute(
            select(Chapter.chapter_number, ChapterVersion)
            .outerjoin(ChapterVersion, Chapter.selected_version_id == ChapterVersion.id)
            .where(Chapter.project_id == project_id, Chapter.chapter_number < chapter_number)
            .order_by(Chapter.chapter_number, Chapter.id)
        )).all()
        state, lineage, coverage = cls.empty(), [], []
        counts = Counter(number for number, _ in rows)
        for number, version in rows:
            if version is None:
                coverage.append({"chapter_number": number, "version_id": None,
                                 "status": "not_requested", "reason": "尚未采用正文"})
                continue
            content_hash = hashlib.sha256((version.content or "").encode()).hexdigest()
            meta = version.metadata if isinstance(version.metadata, dict) else {}
            gate = meta.get("quality_gate")
            gate = gate if isinstance(gate, dict) else {}
            status = gate.get("narrative_delta_status", meta.get("narrative_delta_status", "missing"))
            if not isinstance(status, str):
                status = "invalid"
            reason = gate.get("narrative_delta_reason")
            extraction_source = None
            repair = meta.get("narrative_delta_repair")
            repair = repair if isinstance(repair, dict) else {}
            candidates = []
            if repair.get("narrative_delta") is not None:
                candidates.append((repair, repair.get("narrative_base"), "repair"))
            if gate.get("narrative_delta") is not None:
                candidates.append((gate, meta.get("narrative_base"), "quality_gate"))
            if counts[number] > 1:
                status, reason = "invalid", "同章存在多条采用记录，来源待裁决"
            else:
                for extraction, base, kind in candidates:
                    if extraction.get("status") != "verified":
                        status, reason = "invalid", "叙事抽取尚未验证"
                        continue
                    if extraction.get("content_hash") != content_hash or base != digest(lineage):
                        status, reason = "stale", "正文或前文版本谱系已变化"
                        continue
                    try:
                        if kind == "repair":
                            from .chapter_derivation_service import source_is_current
                            source = extraction.get("source_ref")
                            if not isinstance(source, dict) or not await source_is_current(session, source):
                                status, reason = "stale", "补抽取的采用来源已变化"
                                continue
                        delta = NarrativeDelta.model_validate(extraction["narrative_delta"])
                        cls.validate_evidence(delta, version.content or "", state)
                        state = cls.apply(state, delta.model_dump(), chapter=number, version_id=version.id)
                        status, reason, extraction_source = "ready", None, kind
                        break
                    except (ValueError, TypeError) as exc:
                        status, reason = "invalid", str(exc)[:300]
                if not candidates and status not in {"missing", "invalid", "not_requested", "stale"}:
                    status = "missing"
            coverage.append({"chapter_number": number, "version_id": version.id,
                             "content_hash": content_hash, "status": status,
                             **({"extraction_source": extraction_source} if extraction_source else {}),
                             **({"reason": reason} if reason else {})})
            lineage.append([number, version.id, content_hash])
        ready = sum(item["status"] == "ready" for item in coverage)
        summary = {"status": "ready" if ready == len(coverage) else "partial" if ready else "missing",
                   "total_chapters": len(coverage), "ready_chapters": ready, "chapters": coverage}
        return state, digest(lineage), summary

    @classmethod
    async def load(cls, session, project_id: str, chapter_number: int) -> tuple[dict, str]:
        state, lineage, coverage = await cls._replay(session, project_id, chapter_number)
        state["coverage"] = coverage
        return state, lineage

    @classmethod
    async def view(cls, session, project_id: str, chapter_number: int) -> dict:
        """Read-only author view of canon immediately before this chapter. No repair or LLM calls."""
        state, lineage, coverage = await cls._replay(session, project_id, chapter_number)
        facts = [fact for fact in state["facts"].values()
                 if fact.get("valid_until_chapter") is None or chapter_number <= fact["valid_until_chapter"]]
        promises = list(state["promises"].values())
        return {"project_id": project_id, "chapter_number": chapter_number, "lineage": lineage,
                "facts": facts,
                "relationships": [fact for fact in facts if fact.get("related_entities")],
                "open_promises": [item for item in promises if item["status"] == "open"],
                "closed_promises": [item for item in promises if item["status"] == "closed"],
                "conflicts": list(state["conflicts"].values()),
                "reader": state["reader"], "coverage": coverage,
                "reference_contract": await cls.reference_view(session, project_id)}

    @staticmethod
    async def reference_view(session, project_id: str) -> dict:
        """Expose existing fusion work and its evidence boundary; never synthesize on read."""
        from ..models.novel import NovelProject
        from .reference_novel_library_service import ReferenceNovelLibraryService
        from .reference_reading_contract import is_current
        project = await session.get(NovelProject, project_id)
        ids = list(project.reference_novel_ids or []) if project else []
        if not ids:
            return {"status": "not_configured", "source_kind": "search_analysis", "sources": [],
                    "structure_references": [], "original_full_text_read": False,
                    "evidence_limits": "尚未绑定参考资料。"}
        novels = await ReferenceNovelLibraryService(session).get_by_ids(ids)
        dna = project.fusion_dna
        current = is_current(dna, novels, ids)
        status = (dna.get("generation_status") or "ready") if current else "stale"
        return {"status": status, "source_kind": "search_analysis", "original_full_text_read": False,
                "sources": [{"id": novel.id, "title": novel.title, "status": novel.status} for novel in novels],
                "structure_references": dna.get("structure_references", []) if current else [],
                "evidence_limits": dna.get("evidence_limits", "依据搜索资料与AI分析，不是原著全文阅读。") if current
                    else "绑定或资料已变化，旧融合分工不再作为当前参考依据；尚未重新融合。"}
