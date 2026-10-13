from types import SimpleNamespace

from app.services.mission_builder_service import MissionBuilderService


class _DummyPolicy:
    @staticmethod
    def resolve_word_count_bounds():
        return 2000, 4000, 3000


def test_mission_builder_service_build_fast_chapter_mission():
    service = MissionBuilderService(
        prompt_service=None,
        llm_service=None,
        generation_policy_service=_DummyPolicy(),
    )

    blueprint = SimpleNamespace(
        mission_constraints={
            "must_include": ["关键线索"],
            "scene_list": [{"goal": "推进剧情"}],
            "allowed_new_characters": ["新角色"],
            "pov_character": "林玄",
            "word_budget": {"target": 3200},
        },
        chapter_function="climax",
        chapter_focus="反击开始",
        brief_summary="主角反击",
    )

    mission = service.build_fast_chapter_mission(
        chapter_number=12,
        outline_title="反击",
        outline_summary="主角终于开始反击",
        writing_notes="强化爽点",
        chapter_blueprint=blueprint,
    )

    assert mission["chapter_type"] == "climax"
    assert mission["satisfaction_design"]["type"] == "高潮爆发"
    assert mission["word_budget"]["target"] == 3200
    assert mission["pov"] == "林玄"


def test_lite_director_receives_motives_and_preserves_confirmed_choice():
    import asyncio
    import json
    from unittest.mock import AsyncMock

    focus = {"character_name": "林玄", "choice": "向朋友求助", "cost": "放下逞强"}
    llm = SimpleNamespace(get_llm_response=AsyncMock(return_value=json.dumps({
        "macro_beat": "E", "scene_list": [], "character_focus": {"choice": "独自对抗强敌"},
    })))
    service = MissionBuilderService(SimpleNamespace(get_prompt=AsyncMock(return_value="导演规则")), llm, _DummyPolicy())
    mission = asyncio.run(service.build_lite_chapter_mission(
        chapter_number=2, outline_title="喝茶", outline_summary="接受陪伴", writing_notes="",
        previous_summary="拒绝过帮助", previous_tail="留了一只茶杯",
        chapter_blueprint=SimpleNamespace(mission_constraints={"character_focus": focus}, chapter_function="resolution",
                                         chapter_focus=None, brief_summary=None),
        user_id=1, character_context="最珍惜一起喝茶的日子；怕成为朋友的负担",
    ))
    prompt = llm.get_llm_response.call_args.kwargs["conversation_history"][0]["content"]
    assert "最珍惜一起喝茶的日子" in prompt and "向朋友求助" in prompt
    assert mission["character_focus"] == focus
    assert mission["character_context"] == "最珍惜一起喝茶的日子；怕成为朋友的负担"
    assert llm.get_llm_response.await_count == 1
