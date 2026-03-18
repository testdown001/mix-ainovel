import asyncio
from types import SimpleNamespace

from app.services.standard_generation_flow_service import (
    StandardGenerationFlowResult,
    StandardGenerationFlowService,
)


class _VersionService:
    async def run(self, **kwargs):
        return {
            "versions": [{"content": "版本A", "metadata": {}}],
            "best_version_index": 0,
            "ai_review_result": {"score": 88},
        }


class _PostProcessService:
    async def run(self, **kwargs):
        return {
            "best_content": "处理后正文",
            "review_summaries": {"ai_review": {"score": 88}},
            "stage_b_params": {"project_id": kwargs["project_id"]},
        }


class _CompressionService:
    async def compress_overlength(self, text, *, target_max, user_id):
        return text[:target_max]

    def hard_trim_to_limit(self, text, target_max):
        return text[:target_max]


def test_standard_generation_flow_service_runs_and_marks_stages():
    stages = []
    service = StandardGenerationFlowService(
        session=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        version_generation_service=_VersionService(),
        standard_post_processing_service=_PostProcessService(),
        text_compression_service=_CompressionService(),
    )

    async def _run():
        return await service.run(
            prompt_input="prompt",
            writer_prompt="writer",
            enhanced_context={},
            config=SimpleNamespace(enable_anti_hallucination=False, version_count=1),
            project_id="proj-1",
            chapter_number=6,
            outline_title="标题",
            outline_summary="摘要",
            chapter_mission={"pov": "林峰"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            writer_blueprint={},
            memory_context=None,
            chapter_target_word_count=2000,
            chapter_word_count_min=1000,
            chapter_word_count_max=3000,
            genre_profile=None,
            history_context={"previous_summary": "上章", "completed_chapters": []},
            mark_stage=lambda name, started: stages.append(name),
        )

    result = asyncio.run(_run())

    assert isinstance(result, StandardGenerationFlowResult)
    assert result.best_content == "处理后正文"
    assert result.review_summaries["ai_review"]["score"] == 88
    assert result.stage_b_params["project_id"] == "proj-1"
    assert "generate_versions" in stages
    assert "ai_review" in stages
    assert "stage_a_post_processing" in stages
