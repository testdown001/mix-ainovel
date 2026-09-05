import asyncio
from types import SimpleNamespace

import pytest

from app.services.scene_generation_service import SceneGenerationService


def test_scene_generation_service_build_fallback_scenes():
    scenes = SceneGenerationService.build_fallback_scenes({"word_budget": {"total": 3600}})

    assert len(scenes) == 3
    assert scenes[0]["target_words"] == 900
    assert scenes[2]["target_words"] == 1080
    assert "情绪峰值" not in scenes[2]["goal"]
    assert "刀切" not in scenes[2]["goal"]


def test_scene_generation_service_build_slim_context_and_compress():
    context = SceneGenerationService.build_slim_context(
        {
            "chapter_goals": "目标",
            "mission_brief": "任务书",
            "writer_blueprint": "蓝图",
            "creative_memory": "[已确认创作记忆]\n保持克制的第三人称限知视角",
            "forbidden_characters": "禁角",
        }
    )

    # 叙事性上下文（可压缩）只含叙事项；硬约束已移入 build_hard_constraints 固定段
    assert "任务书" in context
    assert "蓝图" in context
    assert "保持克制的第三人称限知视角" not in context  # 已确认口吻独立传递，不参与背景压缩。
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


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("scene_count", [1, 2])
def test_scene_calls_keep_emotional_intent_after_background_compression(nested, scene_count, monkeypatch):
    calls = []
    checked = []
    token_budgets = []
    monkeypatch.setattr("app.services.scene_generation_service.settings.writer_max_tokens", 8192)

    class LLM:
        async def get_llm_response(self, **kwargs):
            calls.append(kwargs["conversation_history"][0]["content"])
            token_budgets.append(kwargs["max_tokens"])
            return "他收好旧碗，抬头看了师姐一眼。"

    def check(**kwargs):
        checked.append(kwargs)
        return SimpleNamespace(passed=True)

    service = SceneGenerationService(
        LLM(), SimpleNamespace(check=check),
        SimpleNamespace(resolve_temperature=lambda _: 0.7), None,
    )
    intentions = {
        "chapter_type": "余波章",
        "emotion_curve": {"curve": "悲伤渐渐沉静", "breathing_point": "收完碗后静坐"},
        "deliberate_omission": {"what": "不说破旧碗的主人", "why": "留给读者体会"},
        "tone_guide": {"ink_distribution": "略写赶路，详写门口停顿"},
        "scene_list": [
            {"goal": "收拾旧宅", "target_words": 300},
            {
                "goal": "赴约", "target_words": 300, "relationship_temp": "开始接受师姐陪伴",
                "turn": "收回拒绝的话", "end_state": "两人一起出门", "transition_out": "以关门声收住",
                "dialogue_noise": "让没接上的问句停一会儿", "human_texture": ["旧碗仍留着茶渍"],
            },
        ],
    }
    if scene_count == 1:
        intentions["scene_list"] = intentions["scene_list"][1:]
        intentions["scene_list"][0]["target_words"] = 3000
    mission = {"hard_constraints": {"pov": "林玄"}, "soft_suggestions": intentions} if nested else {
        **intentions, "pov": "林玄",
    }
    result = asyncio.run(service.generate_scene_by_scene(
        prompt_sections_data={
            "mission_brief": "背景" * 3000, "previous_tail": "上章结尾",
            "significance": "历史心结：不愿将后背交给师兄",
            "emotional_core": "本书情感核心：珍惜一起吃饭的日子",
            "creative_memory": "选中口吻：让停顿承载关心，口吻样本不是正史",
            "reference_guidance": "参考甲的成长回报+参考乙的关系牵挂；兑现后给情绪留余波",
            "reference_beats": "承诺回收后以态度变化展示回报",
        },
        writer_prompt="按本章功能写作", chapter_mission=mission,
        forbidden_characters=[], allowed_new_characters=[], user_id=1,
    ))
    assert result["metadata"]["scene_count"] == scene_count
    assert len(calls) == scene_count
    if scene_count > 1:
        assert "（上下文已压缩）" in calls[1]
    else:
        assert 4096 < token_budgets[0] <= 8192  # 整章单场景有足够输出空间。
    for prompt in calls:
        for intent in ("余波章", "悲伤渐渐沉静", "收完碗后静坐", "不说破旧碗的主人", "略写赶路，详写门口停顿"):
            assert intent in prompt
        assert "视角(POV)：林玄" in prompt
        assert "不愿将后背交给师兄" in prompt
        assert "珍惜一起吃饭的日子" in prompt
        assert "让停顿承载关心" in prompt and "不是正史" in prompt
        assert "参考甲的成长回报+参考乙的关系牵挂" in prompt
        assert "兑现后给情绪留余波" in prompt
        assert "承诺回收后以态度变化展示回报" in prompt
    for intent in ("开始接受师姐陪伴", "收回拒绝的话", "两人一起出门", "以关门声收住", "让没接上的问句停一会儿", "旧碗仍留着茶渍"):
        assert intent in calls[-1]
    assert checked[0]["pov"] == "林玄"
