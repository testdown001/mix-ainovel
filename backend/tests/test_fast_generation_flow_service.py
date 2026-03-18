import asyncio
from types import SimpleNamespace

from app.services.fast_generation_flow_service import (
    FastGenerationFlowResult,
    FastGenerationFlowService,
)


class _SingleVersionService:
    async def generate(self, **kwargs):
        return {"content": "正文", "metadata": {}}


class _CompressionService:
    async def compress_overlength(self, text, *, target_max, user_id):
        return text[:target_max]

    def hard_trim_to_limit(self, text, target_max):
        return text[:target_max]


def test_fast_generation_flow_service_returns_stage_b_params_and_reviews():
    stages = []
    service = FastGenerationFlowService(
        session=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        single_version_generation_service=_SingleVersionService(),
        text_compression_service=_CompressionService(),
    )

    async def _run():
        return await service.run(
            prompt_input="prompt",
            writer_prompt="writer",
            project_id="proj-1",
            chapter_number=2,
            outline_title="标题",
            outline_summary="摘要",
            chapter_mission={"pov": "林峰"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            writer_blueprint={},
            memory_context=None,
            enhanced_context={},
            config=SimpleNamespace(
                disable_guardrail_rewrite=True,
                enable_lightweight_humanization=False,
                enable_polish=False,
                enable_anti_hallucination=False,
                use_local_anti_hallucination=False,
            ),
            chapter_target_word_count=2000,
            chapter_word_count_max=3000,
            genre_profile=None,
            history_context={"previous_summary": "上章", "completed_chapters": []},
            emit_text_delta=None,
            mark_stage=lambda name, started: stages.append(name),
            run_polish=None,
        )

    result = asyncio.run(_run())

    assert isinstance(result, FastGenerationFlowResult)
    assert result.best_content == "正文"
    assert result.review_summaries["quality_detection"]["status"] == "scheduled_async"
    assert result.stage_b_params["project_id"] == "proj-1"
    assert "generate_fast_version" in stages
