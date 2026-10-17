"""Optional extraction must never make a valid manuscript unusable or add model calls."""
import asyncio
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.generation_quality_gate import GenerationQualityGate, NarrativeCheck
from app.services.narrative_state_service import NarrativeStateService, digest
from app.services.chapter_planning_service import (
    extract_planning_from_item, get_outline_planning, resolve_emotional_intent,
)
from app.services.chapter_mission_context import build_emotional_continuity_brief
from app.services.emotion_deviation_service import EmotionDeviationService

TEXT = "夜雨敲在窗上。林玄收起信，推门走进巷子。" * 12


def delta(**kwargs):
    return dict(focus="林玄", desire="", pressure="", payoff="", aftereffect="", next_pull="", emotion="",
                facts=[], opened=[], closed=[], **kwargs)


@pytest.mark.parametrize("extraction,status", [(None, "missing"), ({"bad": 1}, "invalid"), ("bad", "invalid"), (delta(), "ready")])
def test_optional_delta_never_retries_or_rejects_quality(extraction, status):
    llm = SimpleNamespace(generate_structured=AsyncMock(return_value=NarrativeCheck(
        issues=[], state_delta=[], narrative_delta=extraction)))
    report = asyncio.run(GenerationQualityGate(llm).check(
        text=TEXT, context={"require_narrative_delta": True}, user_id=1))
    assert report["status"] == "verified"
    assert report["narrative_delta_status"] == status
    assert llm.generate_structured.await_count == 1
    assert "NarrativeDelta" in NarrativeCheck.model_json_schema()["$defs"]


def test_invalid_citation_does_not_reject_or_publish_delta():
    extraction = delta()
    extraction["facts"] = [{"entity": "林玄", "attribute": "关系", "value": "相信师姐",
        "evidence": "不存在的证据", "confidence": 0.9, "related_entities": ["师姐"]}]
    llm = SimpleNamespace(generate_structured=AsyncMock(return_value=NarrativeCheck(
        issues=[], state_delta=[], narrative_delta=extraction)))
    report = asyncio.run(GenerationQualityGate(llm).check(
        text=TEXT, context={"require_narrative_delta": True}, user_id=1))
    assert report["status"] == "verified"
    assert report["narrative_delta_status"] == "invalid"
    assert report["narrative_delta"] is None


def test_state_view_quarantines_missing_invalid_and_stale_versions():
    good = delta()
    good["facts"] = [{"entity": "林玄", "attribute": "信任", "value": "信任师姐",
        "evidence": "收起信", "confidence": 0.9, "related_entities": ["师姐"]}]
    content_hash = hashlib.sha256(TEXT.encode()).hexdigest()
    def version(number, metadata):
        return SimpleNamespace(id=number, content=TEXT, metadata=metadata)
    first = version(1, {"narrative_base": digest([]), "quality_gate": {
        "status": "verified", "content_hash": content_hash, "narrative_delta": good}})
    second = version(2, {})
    third = version(3, {"narrative_base": "old", "quality_gate": {
        "status": "verified", "content_hash": content_hash, "narrative_delta": good}})
    fourth = version(4, {"narrative_base": digest([[1,1,content_hash],[2,2,content_hash],[3,3,content_hash]]),
        "quality_gate": {"status": "verified", "content_hash": content_hash, "narrative_delta": {"bad": 1}}})
    session = SimpleNamespace(get=AsyncMock(return_value=None), execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [
        (1, first), (2, second), (3, third), (4, fourth), (5, None)])))
    view = asyncio.run(NarrativeStateService.view(session, "p", 6))
    assert [item["status"] for item in view["coverage"]["chapters"]] == [
        "ready", "missing", "stale", "invalid", "not_requested"]
    assert view["coverage"]["ready_chapters"] == 1
    assert view["relationships"][0]["source_version"] == 1
    assert view["coverage"]["status"] == "partial"
    assert "chapters.chapter_number <" in str(session.execute.await_args.args[0])


def test_emotional_intent_roundtrip_and_precedence():
    planning = extract_planning_from_item({"emotional_intent": "quiet", "reader_effect": "余波中牵挂"})
    assert get_outline_planning({"planning": planning}) == planning
    assert resolve_emotional_intent(planning, {"emotional_intent": "intense"})["emotional_intent"] == "quiet"
    assert resolve_emotional_intent({}, {"chapter_function": "interlude"}, {"emotional_intent": "intense"})["emotional_intent"] == "quiet"
    assert "不得为了通用节奏曲线强加高潮" in build_emotional_continuity_brief(planning)
    assert EmotionDeviationService().compute_deviation_brief(
        [{"chapter_number": 1, "intensity": 10}], [{"chapter_number": 1, "intensity": 1}],
        2, emotional_intent="quiet") is None
    assert "emotional_intent" not in extract_planning_from_item({"emotional_intent": "invalid", "reader_effect": "x"})


def test_explicit_repair_replays_without_forging_a_quality_gate(monkeypatch):
    from app.services import chapter_derivation_service
    extraction = delta()
    extraction['facts'] = [{"entity": "林玄", "attribute": "持有物", "value": "信",
        "evidence": "收起信", "confidence": 0.9, "related_entities": []}]
    repair = {"status": "verified", "content_hash": hashlib.sha256(TEXT.encode()).hexdigest(),
              "narrative_base": digest([]), "narrative_delta": extraction,
              "source_ref": {"source_version_id": 7}}
    version = SimpleNamespace(id=7, content=TEXT, metadata={"narrative_delta_repair": repair})
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(1, version)])))
    monkeypatch.setattr(chapter_derivation_service, "source_is_current", AsyncMock(return_value=True))
    state, _ = asyncio.run(NarrativeStateService.load(session, 'p', 2))
    assert state["coverage"]["chapters"][0]["status"] == "ready"
    assert state["coverage"]["chapters"][0]["extraction_source"] == "repair"
    assert list(state["facts"].values())[0]["value"] == "信"
    assert "quality_gate" not in version.metadata
    monkeypatch.setattr(chapter_derivation_service, "source_is_current", AsyncMock(return_value=False))
    state, _ = asyncio.run(NarrativeStateService.load(session, 'p', 2))
    assert state["facts"] == {}
    assert state["coverage"]["chapters"][0]["status"] == "stale"
