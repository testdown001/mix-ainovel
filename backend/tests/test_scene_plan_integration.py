import asyncio
import json
from types import SimpleNamespace

from app.services.context_planner_service import ContextPlannerService
from app.services.prompt_compiler_service import PromptCompilerService
from app.services.scene_generation_service import SceneGenerationService


def test_prompt_compiler_injects_scene_plan_and_context_strategy():
    plan = asyncio.run(
        ContextPlannerService().build_plan(
            project_id="proj-scene",
            chapter_number=6,
            writing_notes="强化高潮",
            flow_config={"preset": "literary", "enable_rag": True, "enable_power_system": True},
            blueprint={"characters": [{"name": "林玄"}], "chapter_outline": [{"chapter_number": idx} for idx in range(1, 10)]},
            outline_data={"title": "破阵", "summary": "林玄在阵中破局。"},
            history_context={"previous_summary": "阵法已经启动。"},
        )
    )

    compiled = PromptCompilerService().compile_scene_prompt_data(
        plan=plan,
        prompt_sections_data={"chapter_goals": "目标"},
    )

    assert json.loads(compiled["scene_plan"])[0]["scene_id"] == "scene_1"
    assert json.loads(compiled["context_strategy"])["mode"] == "hybrid"


def test_scene_generation_uses_compiled_scene_plan_when_mission_has_no_scene_list():
    calls = []

    class _LLM:
        async def get_llm_response(self, **kwargs):
            calls.append(kwargs["conversation_history"][0]["content"])
            return "林玄在阵中推进。"

    class _Guardrails:
        def check(self, **kwargs):
            return SimpleNamespace(passed=True)

        def apply_local_patches(self, text, result):
            return text

    class _Policy:
        def resolve_temperature(self, chapter_mission):
            return 0.7

    class _Compression:
        def hard_trim_to_limit(self, text, limit):
            return text[:limit]

    service = SceneGenerationService(_LLM(), _Guardrails(), _Policy(), _Compression())
    result = asyncio.run(
        service.generate_scene_by_scene(
            prompt_sections_data={
                "chapter_goals": "目标",
                "scene_plan": json.dumps(
                    [
                        {"scene_id": "scene_1", "goal": "入阵", "target_words": 300, "characters": ["林玄"]},
                        {"scene_id": "scene_2", "goal": "破阵", "target_words": 300, "dependencies": ["scene_1"]},
                    ],
                    ensure_ascii=False,
                ),
            },
            writer_prompt="写作",
            chapter_mission={},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            max_word_count=2000,
        )
    )

    assert result["metadata"]["scene_count"] == 2
    assert result["metadata"]["scene_plan_applied"] is True
    assert "重点人物：林玄" in calls[0]
    assert "依赖场景：scene_1" in calls[1]
