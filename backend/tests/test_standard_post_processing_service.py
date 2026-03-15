import asyncio
from types import SimpleNamespace

from app.services.standard_post_processing_service import StandardPostProcessingService


class _DummyGuardrails:
    def check(self, **kwargs):
        return SimpleNamespace(passed=True)

    def apply_local_patches(self, text, result):
        return text

    def format_violations_for_rewrite(self, result):
        return ""


class _DummyOrchestrator:
    def __init__(self):
        self.session = SimpleNamespace()
        self.llm_service = SimpleNamespace()
        self.prompt_service = SimpleNamespace()
        self.guardrails = _DummyGuardrails()


def test_standard_post_processing_service_minimal_path():
    orchestrator = _DummyOrchestrator()
    service = StandardPostProcessingService(orchestrator)

    config = SimpleNamespace(
        enable_self_critique=False,
        enable_consistency=False,
        enable_humanization=False,
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=False,
        enable_optimizer=False,
        enable_enrichment=False,
        enable_polish=False,
        enable_density_compression=False,
        enable_six_dimension=False,
        humanization_threshold=70,
    )

    result = asyncio.run(
        service.run(
            best_content="正文内容",
            best_version={"metadata": {}},
            ai_review_result=None,
            review_summaries={},
            config=config,
            project_id="proj-1",
            chapter_number=5,
            chapter_mission={"pov": "林玄"},
            writer_blueprint={"characters": []},
            history_context={"previous_summary": "上章摘要", "completed_chapters": []},
            user_id=1,
            chapter_word_count_min=2000,
            chapter_word_count_max=4000,
            chapter_target_word_count=3000,
            enhanced_flow=None,
            outline_title="第五章",
            forbidden_characters=[],
            allowed_new_characters=[],
        )
    )

    assert result["best_content"] == "正文内容"
    assert result["review_summaries"]["quality_detection"]["status"] == "scheduled_async"
    assert result["stage_b_params"]["project_id"] == "proj-1"
