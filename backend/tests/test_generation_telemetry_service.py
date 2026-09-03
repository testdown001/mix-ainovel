import asyncio
import pytest

from app.services.generation_telemetry_service import (
    GenerationTelemetryService,
    record_generation_llm_call,
)
from app.services.writing_archive_service import WritingArchiveService


def test_generation_telemetry_service_emits_middle_product_payload():
    emitted = []

    async def _emit_stream(event, payload=None):
        emitted.append((event, payload))

    service = GenerationTelemetryService(_emit_stream)

    asyncio.run(service.emit_context_plan({"chapter_phase": "climax"}))
    asyncio.run(service.emit_verification_report({"summary": "验证完成"}))

    assert emitted[0][0] == "middle_product"
    assert emitted[0][1]["type"] == "context_plan"
    assert emitted[0][1]["data"]["chapter_phase"] == "climax"
    assert emitted[1][1]["type"] == "verification_report"
    assert emitted[1][1]["data"]["summary"] == "验证完成"


def test_generation_telemetry_summarizes_llm_calls():
    async def _emit_stream(event, payload=None):
        return None

    service = GenerationTelemetryService(_emit_stream)
    record_generation_llm_call({
        "api_type": "default", "status": "success", "duration_ms": 2000,
        "first_token_ms": 300, "prompt_tokens": 120, "completion_tokens": 80,
        "retry_count": 1, "compatibility_fallback_count": 1,
    })
    record_generation_llm_call({
        "api_type": "fallback", "status": "success", "duration_ms": 1000,
        "first_token_ms": 200, "prompt_tokens": 20, "completion_tokens": 20,
        "retry_count": 0, "compatibility_fallback_count": 0,
    })

    summary = service.llm_metrics["summary"]
    assert summary["call_count"] == 2
    assert summary["prompt_tokens"] == 140
    assert summary["completion_tokens"] == 100
    assert summary["first_token_ms"] == 200
    assert summary["retry_count"] == 1
    assert summary["fallback_count"] == 1
    assert summary["compatibility_fallback_count"] == 1
    assert summary["output_tokens_per_second"] == 33.33


@pytest.mark.asyncio
async def test_generation_performance_is_persisted_in_writing_archive(db_session):
    archive_service = WritingArchiveService(db_session)
    archive = await archive_service.create_archive(project_id="telemetry-project", chapter_number=8)
    performance = {
        "stage_timings_ms": {"generate_fast_version": 1250, "total_pipeline": 1800},
        "llm_metrics": {"summary": {"call_count": 1}, "calls": []},
    }

    completed = await archive_service.complete_archive(
        archive.id,
        final_version_id=19,
        version_count=1,
        performance_metrics=performance,
    )
    await db_session.commit()
    await db_session.refresh(completed)

    assert completed.final_output["selected_version"] == 19
    assert completed.final_output["performance"] == performance
