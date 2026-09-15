from app.services.narrative_state_service import NarrativeStateService


def _delta():
    return {
        "focus": "林砚",
        "desire": "拿到钥匙",
        "pressure": "守门人已经认出他",
        "payoff": "钥匙落入掌心",
        "aftereffect": "他发现钥匙上有旧血",
        "next_pull": "查清旧血来自谁",
        "emotion": "从犹豫到决心",
        "facts": [{
            "entity": "林砚", "attribute": "持有物", "value": "钥匙",
            "evidence": "钥匙落入掌心", "supersedes_value": None,
            "valid_until_chapter": None, "confidence": 0.95, "related_entities": [],
        }],
        "opened": [{
            "question": "旧血来自谁", "character": "林砚",
            "expected_payoff_chapter": None, "evidence": "旧血来自谁",
        }],
        "closed": [],
    }


def test_selected_state_is_relevant_and_promises_are_opened():
    state = NarrativeStateService.apply(NarrativeStateService.empty(), _delta(), chapter=3, version_id=11)
    selected = NarrativeStateService.for_scene(state, {"goal": "查旧血", "characters": ["林砚"]}, 4)
    assert selected["facts"][0]["value"] == "钥匙"
    assert selected["open_promises"][0]["question"] == "旧血来自谁"


def test_conflicting_fact_is_quarantined_until_explicit_supersession():
    state = NarrativeStateService.apply(NarrativeStateService.empty(), _delta(), chapter=3, version_id=11)
    changed = _delta()
    changed["facts"][0]["value"] = "断剑"
    changed["facts"][0]["evidence"] = "断剑握在手里"
    state = NarrativeStateService.apply(state, changed, chapter=4, version_id=12)
    assert state["facts"] == {}
    assert state["conflicts"]
