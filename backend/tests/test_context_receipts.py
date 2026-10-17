from app.services.context_receipt_service import build_context_receipt, build_execution_receipt, collect_receipt_sources


def test_receipt_observes_final_input_instead_of_planned_modules():
    actual = "正文证据：" + "林砚握住旧钥匙，师姐却没有回头。" * 8
    clipped = "用于截断测试的事实材料" * 12
    prompt = "[历史证据]\n" + actual + "\n[预算裁剪后]\n" + clipped[:80]
    receipt = build_context_receipt(system_prompt="writer", user_prompt=prompt, sources=[
        {"kind": "fact", "text": actual, "source_ref": {"source_version_id": 7}},
        {"kind": "fact", "text": clipped, "source_ref": {"source_version_id": 8}},
        {"kind": "planned", "text": "不在最终输入中的未来章纲"},
    ])
    assert [item["injection_status"] for item in receipt["evidence"]] == ["included", "partial", "omitted"]
    assert receipt["evidence"][0]["source_ref"]["source_version_id"] == 7
    assert receipt["actual_injection"] == {"included": 1, "partial": 1, "omitted": 1}
    assert "not_in_final_prompt" == receipt["evidence"][2]["reason"]
    assert all("text" not in item for item in receipt["evidence"])
    assert receipt["user_chars"] == len(prompt)
    assert len(receipt["user_prompt_sha256"]) == 64
    assert receipt["observed_sections"][0]["title"] == "[历史证据]"


def test_execution_separates_reports_modifications_background_and_skips():
    receipt = build_execution_receipt({"quality_gate": {"status": "verified", "narrative_delta_status": "missing"},
        "review_summaries": {"polish": {"applied": True}, "compression": {"applied": False, "rolled_back": True},
            "reader_simulator": {"status": "scheduled_async"}, "time_budget": {"skipped": ["review"]}}})
    steps = {item["step"]: item for item in receipt["steps"]}
    assert steps["quality_gate"]["status"] == "report_completed"
    assert not steps["quality_gate"]["text_modified"]
    assert steps["review_summaries.polish"]["text_modified"]
    assert steps["review_summaries.compression"]["status"] == "rolled_back"
    assert steps["review_summaries.reader_simulator"]["status"] == "scheduled_async"
    assert steps["review"]["status"] == "budget_skipped"
    assert build_execution_receipt({})["status"] == "unknown"


def test_sources_preserve_scope_without_retaining_secrets_or_entire_metadata():
    sources = collect_receipt_sources({"chunk_records": [{"content": "已采用原文", "chapter_number": 3,
        "metadata": {"source_version_id": 7, "project_id": "p", "irrelevant": "not persisted"}}]})
    assert sources[0]["source_ref"] == {"source_version_id": 7, "project_id": "p"}
    assert build_context_receipt(system_prompt="", user_prompt="已采用原文", sources=sources)["actual_injection"]["included"] == 1
