import asyncio

from app.services.context_planner_service import ContextPlannerService, EvidenceItem, GenerationEvidencePack
from app.services.evidence_router_service import EvidenceRouterService
from app.services.narrative_claim_service import ClaimVerifierService
from app.services.narrative_verifier_service import NarrativeVerifierService
from app.services.novel_bench_service import NovelBenchCase, NovelBenchLiteService


def _build_plan():
    return asyncio.run(
        ContextPlannerService().build_plan(
            project_id="proj-claim",
            chapter_number=8,
            writing_notes="回收旧线索并让林玄突破",
            flow_config={
                "preset": "platinum",
                "enable_rag": True,
                "enable_foreshadowing": True,
                "enable_power_system": True,
                "enable_consistency": True,
                "enable_six_dimension": True,
            },
            blueprint={
                "characters": [{"name": "林玄"}, {"name": "苏璃"}],
                "chapter_outline": [{"chapter_number": idx} for idx in range(1, 12)],
            },
            outline_data={"title": "旧线回响", "summary": "林玄回收旧线索并突破玄元境。"},
            history_context={"previous_summary": "林玄发现了旧线索。"},
        )
    )


def test_claim_verifier_flags_high_impact_claim_without_evidence():
    plan = _build_plan()
    report = ClaimVerifierService().verify(
        chapter_text="林玄回收了旧线索，并在雨夜突破玄元境。",
        plan=plan,
        evidence_summary={"category_counts": {}, "top_titles": []},
    )

    assert report["status"] == "failed"
    assert report["blocking_count"] >= 1
    assert any(item["claim_type"] == "power_state_change" for item in report["claims"])


def test_claim_verifier_supports_power_and_foreshadowing_with_evidence_samples():
    plan = _build_plan()
    report = ClaimVerifierService().verify(
        chapter_text="林玄回收了旧线索，并在雨夜突破玄元境。",
        plan=plan,
        evidence_summary={
            "category_counts": {"symbolic_items": 1, "state_items": 1},
            "evidence_samples": [
                {"category": "symbolic_items", "title": "旧线索", "content": "林玄旧线索指向玄元境突破。"}
            ],
        },
    )

    assert report["status"] == "passed"
    assert report["blocking_count"] == 0


def test_narrative_verifier_runs_claim_level_task():
    plan = _build_plan()
    result = NarrativeVerifierService().verify(
        plan=plan,
        chapter_text="林玄回收了旧线索，并在雨夜突破玄元境。",
        evidence_summary={
            "category_counts": {"symbolic_items": 1, "state_items": 1},
            "evidence_samples": [
                {"category": "symbolic_items", "title": "旧线索", "content": "林玄旧线索指向玄元境突破。"}
            ],
        },
    )

    claim_task = next(item for item in result["tasks"] if item["task"] == "claim_level_verification")
    assert claim_task["status"] == "passed"
    assert claim_task["details"]["claim_count"] > 0


def test_evidence_router_summary_includes_samples_for_claim_verification():
    plan = _build_plan()
    pack = GenerationEvidencePack(
        symbolic_items=[
            EvidenceItem(
                source="foreshadowing",
                title="旧线索",
                content="林玄旧线索指向玄元境突破。",
                score=0.9,
            )
        ]
    )

    summary = EvidenceRouterService().build_summary(plan=plan, evidence_pack=pack)

    assert summary["evidence_samples"][0]["category"] == "symbolic_items"
    assert "玄元境" in summary["evidence_samples"][0]["content"]


def test_novel_bench_lite_scores_fixed_snapshot():
    plan = _build_plan()
    case = NovelBenchCase(
        case_id="claim-lite-001",
        project_id="proj-claim",
        chapter_number=8,
        target_min_chars=10,
        target_max_chars=200,
        must_include=["林玄", "旧线索"],
    )
    result = NovelBenchLiteService().evaluate_case(
        case=case,
        chapter_text="林玄回收了旧线索，并在雨夜突破玄元境。",
        plan=plan,
        evidence_summary={
            "category_counts": {"symbolic_items": 1, "state_items": 1},
            "evidence_samples": [
                {"category": "symbolic_items", "title": "旧线索", "content": "林玄旧线索指向玄元境突破。"}
            ],
        },
    )

    assert result["status"] == "passed"
    assert result["score"] >= 70
