import asyncio
from types import SimpleNamespace

from app.services.literary_generation_flow_service import (
    LiteraryGenerationFlowResult,
    LiteraryGenerationFlowService,
)


class _SceneService:
    async def generate_scene_by_scene(self, **kwargs):
        return {"content": "正文", "metadata": {}}


class _CompressionService:
    async def compress_overlength(self, text, *, target_max, user_id):
        return text[:target_max]

    def hard_trim_to_limit(self, text, target_max):
        return text[:target_max]


class _Guardrails:
    def check(self, **kwargs):
        return SimpleNamespace(passed=True)

    def apply_local_patches(self, text, result):
        return text


def test_literary_generation_flow_service_returns_payload_and_reviews():
    stages = []
    service = LiteraryGenerationFlowService(
        session=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        scene_generation_service=_SceneService(),
        generation_policy_service=SimpleNamespace(
            resolve_literary_postprocess_profile=lambda **kwargs: {
                "enable_prose_sculpting": False,
                "enable_golden_paragraph": False,
                "enable_humanization": False,
            }
        ),
        text_compression_service=_CompressionService(),
        guardrails=_Guardrails(),
    )

    async def _run():
        return await service.run(
            voice_samples_task=None,
            context_plan=SimpleNamespace(),
            prompt_compiler=SimpleNamespace(compile_scene_prompt_data=lambda **kwargs: kwargs["prompt_sections_data"]),
            prompt_sections_data={"chapter_goals": "目标"},
            writer_prompt="writer",
            chapter_mission={"pov": "林峰"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            genre_profile=None,
            chapter_word_count_max=3000,
            chapter_target_word_count=2000,
            chapter_word_count_min=1000,
            config=SimpleNamespace(enable_six_dimension=True, enable_anti_hallucination=False, humanization_threshold=70),
            outline_title="标题",
            history_context={"previous_summary": "上章", "completed_chapters": []},
            project_id="proj-1",
            chapter_number=5,
            enhanced_context={"writer_persona": "人格"},
            run_enrichment=lambda *args, **kwargs: asyncio.sleep(0, result=(args[0], None)),
            run_quality_detection=lambda *args, **kwargs: asyncio.sleep(0, result={"overall_score": 85}),
            mark_stage=lambda name, started: stages.append(name),
        )

    result = asyncio.run(_run())

    assert isinstance(result, LiteraryGenerationFlowResult)
    assert result.best_content == "正文"
    assert result.review_summaries["quality_detection"]["overall_score"] == 85
    assert result.six_dimension_payload["project_id"] == "proj-1"
    assert "generate_scene_by_scene" in stages
