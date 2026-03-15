from app.services.generation_result_service import GenerationResultService


def test_generation_result_service_attaches_verification_report():
    service = GenerationResultService()
    versions = [{"metadata": {}}]
    variants = [{"metadata": {}}]
    report = {"summary": "验证通过"}

    service.attach_verification_report(
        verification_report=report,
        versions=versions,
        variants=variants,
        best_version_index=0,
    )

    assert versions[0]["metadata"]["verification_report"] == report
    assert variants[0]["metadata"]["verification_report"] == report


def test_generation_result_service_builds_debug_metadata_and_response():
    service = GenerationResultService()
    debug_metadata = service.build_debug_metadata(
        version_count=2,
        mode="fast_single_pass",
        stage_flags={"rag": True},
        rag_stats={"chunks": 3},
        context_plan={"chapter_phase": "climax"},
        retrieval_evidence_summary={"total_items": 5},
        prompt_compile_summary={"section_count_after": 7},
        verification_report={"summary": "验证完成"},
        stage_timings_ms={"total_pipeline": 1234},
        strategy_warnings=["风格约束冲突"],
    )

    payload = service.build_response_payload(
        project_id="proj-1",
        chapter_number=8,
        preset="platinum",
        best_version_index=1,
        variants=[{"index": 1, "content": "正文"}],
        review_summaries={"ai_review": {"score": 88}},
        debug_metadata=debug_metadata,
    )

    assert payload["project_id"] == "proj-1"
    assert payload["best_version_index"] == 1
    assert payload["debug_metadata"]["mode"] == "fast_single_pass"
    assert payload["debug_metadata"]["verification_report"]["summary"] == "验证完成"
