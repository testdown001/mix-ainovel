"""Version-bound story facts and reader promises. Drafts never mutate canonical memory."""
from __future__ import annotations

import hashlib
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
            if "".join(item.evidence.split()) not in compact:
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
    async def load(cls, session, project_id: str, chapter_number: int) -> tuple[dict, str]:
        from ..models.novel import Chapter, ChapterVersion
        rows = (await session.execute(
            select(Chapter.chapter_number, ChapterVersion)
            .join(ChapterVersion, Chapter.selected_version_id == ChapterVersion.id)
            .where(Chapter.project_id == project_id, Chapter.chapter_number < chapter_number)
            .order_by(Chapter.chapter_number, Chapter.id)
        )).all()
        state, lineage = cls.empty(), []
        for number, version in rows:
            content_hash = hashlib.sha256((version.content or "").encode()).hexdigest()
            meta = version.metadata if isinstance(version.metadata, dict) else {}
            gate = meta.get("quality_gate") or {}
            # Regenerating/editing an earlier selected chapter invalidates downstream derived state.
            if (gate.get("status") == "verified" and gate.get("content_hash") == content_hash
                    and meta.get("narrative_base") == digest(lineage) and gate.get("narrative_delta")):
                delta = NarrativeDelta.model_validate(gate["narrative_delta"])
                cls.validate_evidence(delta, version.content, state)
                state = cls.apply(state, delta.model_dump(), chapter=number, version_id=version.id)
            lineage.append([number, version.id, content_hash])
        return state, digest(lineage)
