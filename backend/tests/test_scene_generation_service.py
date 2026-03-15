from app.services.scene_generation_service import SceneGenerationService


def test_scene_generation_service_build_fallback_scenes():
    scenes = SceneGenerationService.build_fallback_scenes({"word_budget": {"total": 3600}})

    assert len(scenes) == 3
    assert scenes[0]["target_words"] == 900
    assert scenes[2]["target_words"] == 1080


def test_scene_generation_service_build_slim_context_and_compress():
    context = SceneGenerationService.build_slim_context(
        {
            "chapter_goals": "目标",
            "mission_brief": "任务书",
            "writer_blueprint": "蓝图",
            "forbidden_characters": "禁角",
        }
    )

    assert "目标" in context
    assert "任务书" in context

    compressed = SceneGenerationService.compress_context("x" * 20, max_len=10)
    assert compressed.endswith("（上下文已压缩）")
