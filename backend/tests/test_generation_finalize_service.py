import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.generation_finalize_service import GenerationFinalizeService


def test_generation_finalize_service_build_variant_helpers():
    service = GenerationFinalizeService(
        generation_background_task_service=SimpleNamespace(),
        narrative_verifier=SimpleNamespace(),
        generation_result_service=SimpleNamespace(),
        generation_policy_service=SimpleNamespace(),
    )

    single = service.build_single_variant(
        version_model=SimpleNamespace(id=7),
        version={"content": "正文", "metadata": {"x": 1}},
    )
    multi = service.build_variants(
        versions_models=[SimpleNamespace(id=1), SimpleNamespace(id=2)],
        versions=[{"content": "A", "metadata": {}}, {"content": "B", "metadata": {}}],
    )

    assert single[0]["version_id"] == 7
    assert multi[1]["content"] == "B"


def test_generation_finalize_service_complete_archive_uses_explicit_gatekeeper_score():
    archive_service = SimpleNamespace(complete_archive=AsyncMock())
    service = GenerationFinalizeService(
        generation_background_task_service=SimpleNamespace(),
        narrative_verifier=SimpleNamespace(),
        generation_result_service=SimpleNamespace(),
        generation_policy_service=SimpleNamespace(),
    )

    asyncio.run(
        service.complete_archive(
            archive_service=archive_service,
            archive_id=9,
            variants=[{"version_id": 3}],
            versions_models=[SimpleNamespace(id=3)],
            best_version_index=0,
            version_count=1,
            gatekeeper_score=88,
            warning_label="archive failed",
        )
    )

    archive_service.complete_archive.assert_awaited_once_with(
        9,
        final_version_id=3,
        version_count=1,
        gatekeeper_score=88,
    )


def test_generation_finalize_service_finalize_response_emits_verification():
    verifier = SimpleNamespace(verify=lambda **kwargs: {"summary": "ok"})
    attached = {}
    result_service = SimpleNamespace(
        build_debug_metadata=lambda **kwargs: {"mode": kwargs.get("mode"), "verification_report": kwargs["verification_report"]},
        build_response_payload=lambda **kwargs: {"variants": kwargs["variants"], "debug_metadata": kwargs["debug_metadata"]},
    )
    result_service.attach_verification_report = lambda **kwargs: attached.update(kwargs)
    telemetry = SimpleNamespace(
        emit_verification_report=AsyncMock(),
        llm_metrics={"summary": {"call_count": 1}, "calls": []},
    )

    service = GenerationFinalizeService(
        generation_background_task_service=SimpleNamespace(),
        narrative_verifier=verifier,
        generation_result_service=result_service,
        generation_policy_service=SimpleNamespace(build_stage_flags=lambda config: {"rag": True}),
    )

    async def _emit_completed():
        return None

    result = asyncio.run(
        service.finalize_response(
            plan=SimpleNamespace(),
            chapter_text="正文",
            review_summaries={"ai_review": {"score": 88}},
            retrieval_evidence_summary={"total_items": 3},
            versions=[{"metadata": {}}],
            variants=[{"index": 0, "metadata": {}}],
            best_version_index=0,
            telemetry=telemetry,
            emit_completed=_emit_completed,
            project_id="proj-1",
            chapter_number=4,
            preset="platinum",
            mode="fast_single_pass",
            config=SimpleNamespace(),
            rag_stats={"chunks": 2},
            context_plan_payload={"chapter_phase": "climax"},
            prompt_compile_summary={"compiled": True},
            stage_timings_ms={"total_pipeline": 100},
            strategy_warnings=[],
        )
    )

    telemetry.emit_verification_report.assert_awaited_once()
    assert attached["verification_report"]["summary"] == "ok"
    assert result["debug_metadata"]["mode"] == "fast_single_pass"


def test_generation_finalize_service_complete_progress(monkeypatch):
    from app.services import generation_finalize_service as module

    progress = SimpleNamespace(
        update_stage=AsyncMock(),
        complete=AsyncMock(),
    )
    monkeypatch.setattr(module, "progress_service", progress)

    service = GenerationFinalizeService(
        generation_background_task_service=SimpleNamespace(),
        narrative_verifier=SimpleNamespace(),
        generation_result_service=SimpleNamespace(),
        generation_policy_service=SimpleNamespace(),
    )

    asyncio.run(
        service.complete_progress(
            project_id="proj-1",
            chapter_number=11,
            message="章节生成完成",
        )
    )

    progress.update_stage.assert_awaited_once()
    progress.complete.assert_awaited_once_with("proj-1", 11, success=True)
