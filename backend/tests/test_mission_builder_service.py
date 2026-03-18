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
