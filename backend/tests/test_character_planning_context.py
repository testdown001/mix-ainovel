from copy import deepcopy

from app.services.character_planning_context import (
    CHARACTER_FOCUS_FIELDS,
    build_character_planning_context,
    clean_character_focus,
)
from app.services.chapter_planning_service import get_outline_planning, normalize_outline_metadata


def test_character_context_keeps_motives_relationships_and_promises_within_budget():
    blueprint = {
        "characters": [{"name": "小夏", "identity": "药铺学徒", "goals": "保住药铺",
                        "personality": "逞强但不愿给师父添麻烦", "flaw": "不肯求助"}],
        "relationships": [{"character_from": "小夏", "character_to": "师父", "description": "对药的来源彼此心知肚明"}],
    }
    dossier = {
        "protagonist": {"name": "小夏", "desire": "替师父留下药铺", "flaw": "把求助当成拖累别人"},
        "emotional_core": {"cherished": "一起关门后喝茶的日子", "hard_choice": "坦白药的来源还是保住师父的信任"},
        "anticipation": {"ten_chapters": "主动向师父求助", "fifty_chapters": "共同守住药铺", "long_term": "能够坦诚相待"},
    }
    planning = {"character_focus": {"character_name": "小夏", "wants": "给师父治病",
                "stakes": "不想再失去一个家", "choice": "留下来源不明的药",
                "cost": "隐瞒真相", "relationship_change": "师父没有拆穿", "next_expectation": "她会何时坦白"}}
    original = deepcopy((blueprint, dossier, planning))
    context = build_character_planning_context(blueprint, dossier, planning, query="小夏给师父送药", max_chars=3000)
    assert len(context) <= 3000
    for value in ("把求助当成拖累别人", "一起关门后喝茶", "对药的来源彼此心知肚明", "能够坦诚相待"):
        assert value in context
    for label in CHARACTER_FOCUS_FIELDS.values():
        assert label in context
    assert "不是已发生事实" in context
    assert (blueprint, dossier, planning) == original


def test_long_material_does_not_evict_last_emotional_or_long_term_field():
    dossier = {
        "protagonist": {key: key + "长" * 600 for key in ("name", "identity", "desire", "flaw", "predicament", "charm_point")},
        "emotional_core": {key: key + "长" * 600 for key in ("cherished", "exception", "key_relationship", "hard_choice", "emotional_promise")},
        "anticipation": {key: key + "长" * 600 for key in ("ten_chapters", "fifty_chapters", "long_term")},
    }
    context = build_character_planning_context({}, dossier, max_chars=3000)
    assert len(context) <= 3000
    for value in ("缺陷：flaw", "读者站在他这边的依据：charm_point", "情感承诺：emotional_promise", "长线期待：long_term"):
        assert value in context


def test_context_prefers_scene_characters_and_tolerates_legacy_empty_material():
    blueprint = {"characters": [{"name": f"角色{i}", "goals": "留下自己的选择"} for i in range(10)]}
    context = build_character_planning_context(blueprint, query="角色9向师父坦白", max_chars=1000)
    assert '"name": "角色9"' in context
    assert build_character_planning_context({"characters": None, "relationships": None}) == ""
    assert build_character_planning_context({}, {"dossier": {"emotional_core": {"cherished": "旧茶杯"}}})
    assert build_character_planning_context({}, max_chars=0) == ""


def test_focus_cleaning_and_metadata_migration_preserve_unrelated_data():
    assert clean_character_focus({"wants": "  回家  ", "cost": [], "unknown": "不接收"}) == {"wants": "回家"}
    metadata = {"emotion_hook": "安静的牵挂", "character_focus": {"wants": "回家"},
                "planning": {"emotion_hook": "现在的牵挂"}, "prediction": {"hits": 3}, "scenes": [1, 2]}
    normalized = normalize_outline_metadata(metadata)
    assert normalized["planning"] == {"emotion_hook": "现在的牵挂", "character_focus": {"wants": "回家"}}
    assert normalized["prediction"] == {"hits": 3}
    assert normalized["scenes"] == [1, 2]
    assert "emotion_hook" not in normalized
    assert get_outline_planning(normalized) == get_outline_planning(metadata)
    assert normalize_outline_metadata(normalized) == normalized


def test_legacy_focus_wrong_types_are_safe_at_the_planning_read_boundary():
    for value in ("历史文本", ["人物选择"], 7, None):
        for metadata in ({"character_focus": value}, {"planning": {"character_focus": value}}):
            planning = get_outline_planning(metadata)
            assert planning["character_focus"] == {}
            assert planning["character_focus"].get("character_name") is None


def test_character_review_defect_is_not_averaged_away_but_legacy_reports_remain_compatible():
    from app.schemas.concept_dossier import BlueprintReviewReport

    report = BlueprintReviewReport(total_score=93, dimension_scores={"character_attachment": 35}, issues=[{
        "dimension": "character_attachment", "severity": "高", "target": "chapters:2-3",
        "problem": "两次行动都与主角珍惜的关系无关", "fix_hint": "让行动产生已铺垫的关系后果",
    }])
    assert report.needs_revision(70)
    assert not BlueprintReviewReport(total_score=93, dimension_scores={"opening_strength": 90}).needs_revision(70)
    report.issues[0].target = ""
    assert not report.needs_revision(70)


def test_full_director_receives_character_motives_without_an_extra_generation_call():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.services.writer_shared import generate_chapter_mission

    llm = SimpleNamespace(get_llm_response=AsyncMock(return_value='{"macro_beat":"E","scene_list":[]}'),
                          _resolve_grader_llm_config=AsyncMock(return_value=None))
    prompt_service = SimpleNamespace(get_prompt=AsyncMock(return_value="导演规则"))
    mission = asyncio.run(generate_chapter_mission(
        llm, prompt_service, blueprint_dict={"characters": [{"name": "小夏", "goals": "保住药铺",
                                                             "personality": "嘴硬却会替师父留茶"}]},
        previous_summary="", previous_tail="", outline_title="喝茶", outline_summary="向师父坦白",
        writing_notes="", introduced_characters=["小夏"], all_characters=["小夏"], blueprint_constraints="",
        user_id=1,
    ))
    prompt = llm.get_llm_response.call_args.kwargs["conversation_history"][0]["content"]
    assert "嘴硬却会替师父留茶" in prompt and "保住药铺" in prompt
    assert "嘴硬却会替师父留茶" in mission["character_context"]
    assert llm.get_llm_response.await_count == 1
