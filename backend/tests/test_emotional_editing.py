from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.emotional_editing_service import (
    EmotionalReview, LocalEdit, RevisionPlan, apply_revision_plan, grounded_review,
    review_chapter_quality, text_hash,
)
from app.services.pipeline_review import PipelineReviewMixin
from app.services.reader_simulator_service import ReaderSimulatorService, ReaderType, select_reader_types
from app.services.standard_post_processing_service import StandardPostProcessingService

TEXT = "她把那只缺口的碗推到自己面前。\n“你用好的。”\n他很难过。\n" + "院外有人叫他，他应了一声，手却仍扶着碗沿。" * 8
QUOTE = "“你用好的。”"


def plan(edits=None, protected=True, issues=None):
    return RevisionPlan(emotional_review=EmotionalReview(
        summary="让在意落在动作里，保留不说破的关心。", issues=issues or [],
        protected_passages=[{"quote": QUOTE, "reason": "不解释关心，留给读者体会"}] if protected else [],
    ), edits=edits if edits is not None else [LocalEdit(before="他很难过。", after="他伸出手，又缩了回去。", reason="接住递碗后的迟疑")])


def test_local_edit_keeps_every_unedited_character_and_records_comparison():
    result, report = apply_revision_plan(TEXT, plan())
    assert result == TEXT.replace("他很难过。", "他伸出手，又缩了回去。")
    assert report["applied"] is True
    assert report["edits"][0]["before"] == "他很难过。"
    assert report["result_sha256"] == text_hash(result)
    assert QUOTE in result


@pytest.mark.parametrize("edits,reason", [
    ([{"before": "不存在的句子", "after": "一句话。", "reason": "错位"}], "ambiguous_or_missing_anchor"),
    ([{"before": "院外有人叫他", "after": "门外有人叫他", "reason": "重复定位"}], "ambiguous_or_missing_anchor"),
    ([{"before": "她把那只缺口的碗", "after": "她把碗", "reason": "压缩"},
      {"before": "那只缺口的碗推到", "after": "碗推到", "reason": "压缩"}], "overlapping_edits"),
    ([{"before": QUOTE, "after": "她解释说，自己很关心他。", "reason": "解释"}], "protected_passage_changed"),
    ([{"before": TEXT, "after": "短篇。", "reason": "整章替换"}], "edit_scope_exceeded"),
    ([{"before": "他很难过。", "after": "修订说明：补足情绪。", "reason": "输出污染"}], "invalid_replacement_text"),
])
def test_invalid_plan_is_atomic(edits, reason):
    result, report = apply_revision_plan(TEXT, plan(edits))
    assert result == TEXT
    assert report["applied"] is False
    assert report["reason"] == reason
    assert report["edits"] == []


def test_missing_history_is_not_permission_to_invent_backstory():
    p = plan(issues=[{"quote": "他很难过。", "reason": "不知旧怨", "dimension": "character_choice",
                     "status": "context_needed", "suggestion": "核对前文"}])
    assert apply_revision_plan(TEXT, p)[1]["reason"] == "context_needed"


def test_unverifiable_review_quotes_are_discarded():
    review = plan().emotional_review
    review.protected_passages.append(type(review.protected_passages[0])(quote="模型捏造的对白", reason="并不存在"))
    result = grounded_review(review, TEXT)
    assert result["discarded_unverifiable_quotes"] == 1
    assert len(result["protected_passages"]) == 1


def test_no_edits_and_limit_zero_are_not_rewrite_requests():
    text, report = apply_revision_plan(TEXT, plan([]), max_word_count=0)
    assert text == TEXT and report["applied"] is False
    assert report["reason"] == "no_actionable_edits"
    assert apply_revision_plan(TEXT, plan(), max_word_count=len(TEXT))[1]["reason"] == "word_limit"


@pytest.mark.asyncio
async def test_combined_revision_uses_one_structured_call_and_nested_intent():
    mixin = PipelineReviewMixin()
    mixin.llm_service = SimpleNamespace(generate_structured=AsyncMock(return_value=plan()))
    result, report = await mixin._run_combined_revision(
        TEXT, critical_flaws=[], refinement_suggestions="", enable_self_critique=True,
        chapter_mission={"soft_suggestions": {"chapter_function": "余波", "deliberate_omission": "不说破旧怨"}}, user_id=1)
    assert report["applied"] and result != TEXT
    call = mixin.llm_service.generate_structured.call_args.kwargs
    assert "不说破旧怨" in call["prompt"] and "余波" in call["prompt"]
    assert call["max_validation_retries"] == 0
    mixin.llm_service.generate_structured.assert_awaited_once()


@pytest.mark.asyncio
async def test_oversized_quality_input_is_explicitly_unavailable():
    llm = SimpleNamespace(generate_structured=AsyncMock())
    report = await review_chapter_quality(llm, "字" * 30001, chapter_mission=None, recent_patterns="", user_id=1)
    assert report["status"] == "unavailable"
    llm.generate_structured.assert_not_called()


@pytest.mark.parametrize("intent,third", [("关系余波", ReaderType.CASUAL), ("mystery", ReaderType.HARDCORE), ("climax", ReaderType.THRILL_SEEKER)])
def test_reader_mix_keeps_emotional_reader_without_extra_calls(intent, third):
    types = select_reader_types({"soft_suggestions": {"chapter_function": intent}})
    assert types == [ReaderType.EMOTIONAL, ReaderType.CRITIC, third]


@pytest.mark.asyncio
async def test_reader_failure_is_not_a_score_or_mandatory_thrill_quota():
    llm = SimpleNamespace(get_llm_response=AsyncMock(side_effect=RuntimeError("offline")))
    service = ReaderSimulatorService(None, llm, None)
    report = await service.simulate_reading_experience(TEXT, 3, chapter_mission={"chapter_function": "余波"})
    assert report["status"] == "unavailable"
    assert report["overall_score"] is None
    assert report["recommendations"] == []
    assert llm.get_llm_response.await_count == 5


@pytest.mark.asyncio
async def test_single_reader_reads_late_aftermath_and_mission():
    llm = SimpleNamespace(get_llm_response=AsyncMock(return_value='{"satisfaction":80,"abandon_risk":2}'))
    service = ReaderSimulatorService(None, llm, None)
    await service._simulate_single_reader("前情" * 4000 + "末尾的递碗", 3, ReaderType.EMOTIONAL, [], None, 1,
                                          chapter_mission={"chapter_function": "余波"})
    prompt = llm.get_llm_response.call_args.kwargs["conversation_history"][0]["content"]
    assert "末尾的递碗" in prompt and "余波" in prompt
    assert "未提供前文" in prompt


async def run_post(orch, *, max_words=4000, **flags):
    config = SimpleNamespace(**{**dict.fromkeys([
        "enable_self_critique", "enable_consistency", "enable_humanization", "enable_reader_sim",
        "enable_anti_hallucination", "use_local_anti_hallucination", "enable_optimizer", "enable_polish",
        "enable_enrichment", "enable_density_compression", "enable_six_dimension"], False), **flags}, humanization_threshold=70)
    return await StandardPostProcessingService(orch).run(
        best_content=TEXT, best_version={"metadata": {}}, ai_review_result=None, review_summaries={}, config=config,
        project_id="p", chapter_number=3, chapter_mission=None, writer_blueprint={}, history_context={"previous_summary": ""},
        user_id=1, chapter_word_count_min=0, chapter_word_count_max=max_words, chapter_target_word_count=3000,
        enhanced_flow=None, outline_title="余波", forbidden_characters=[], allowed_new_characters=[])


@pytest.mark.asyncio
@pytest.mark.parametrize("step", ["optimizer", "polish", "humanization", "enrichment", "density_compression"])
async def test_later_style_step_cannot_erase_strength(monkeypatch, step):
    from app.services.humanization_service import HumanizationService
    original_plan = plan([])
    orch = SimpleNamespace(session=None, llm_service=None,
        _run_combined_revision=AsyncMock(return_value=apply_revision_plan(TEXT, original_plan)))
    flags = {"enable_self_critique": True, "enable_" + step: True}
    bad = TEXT.replace(QUOTE, "她把心里的关怀都解释了一遍。")
    if step == "humanization":
        monkeypatch.setattr(HumanizationService, "apply_rule_fixes", lambda *args: bad)
        monkeypatch.setattr(HumanizationService, "humanize", AsyncMock(return_value=bad))
    else:
        setattr(orch, "_run_" + step, AsyncMock(return_value=(bad, {"applied": True})))
    if step == "optimizer":
        flags["enable_polish"] = True
    result = await run_post(orch, max_words=len(TEXT) if step == "density_compression" else 4000, **flags)
    assert result["best_content"] == TEXT
    assert result["stage_b_params"]["analysis_snapshot"] == TEXT
    if step in ("optimizer", "polish"):
        assert result["review_summaries"]["polish"]["applied"] is False
    assert result["review_summaries"]["passage_preservation"]["events"]


@pytest.mark.asyncio
async def test_factual_correction_retires_obsolete_protection_and_final_snapshot():
    corrected = TEXT.replace(QUOTE, "“您用好的。”")
    final = corrected.replace("他很难过。", "他摸了摸碗沿。")
    orch = SimpleNamespace(
        _run_combined_revision=AsyncMock(return_value=apply_revision_plan(TEXT, plan([]))),
        _run_consistency_check=AsyncMock(return_value=(corrected, {"auto_fix_applied": True})),
        _run_polish=AsyncMock(return_value=(final, {"applied": True})))
    result = await run_post(orch, enable_self_critique=True, enable_consistency=True, enable_polish=True)
    assert result["best_content"] == final
    assert result["stage_b_params"]["analysis_snapshot"] == final
    assert not orch._run_polish.call_args.kwargs.get("protected_passages")
