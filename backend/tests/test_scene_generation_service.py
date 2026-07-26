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

    # 叙事性上下文（可压缩）只含叙事项；硬约束已移入 build_hard_constraints 固定段
    assert "任务书" in context
    assert "蓝图" in context
    assert "目标" not in context
    assert "禁角" not in context

    compressed = SceneGenerationService.compress_context("x" * 20, max_len=10)
    assert compressed.endswith("（上下文已压缩）")


def test_scene_generation_service_build_hard_constraints():
    hard = SceneGenerationService.build_hard_constraints(
        {"chapter_goals": "[当前章节目标]\n标题：破阵", "forbidden_characters": "李逆天, 王魔尊"},
        {"pov": "林峰"},
    )

    assert "[当前章节目标]" in hard
    assert "李逆天, 王魔尊" in hard
    assert "林峰" in hard

    # 无任何硬约束输入 → 空段（不注入空标题）
    assert SceneGenerationService.build_hard_constraints({}, None) == ""
