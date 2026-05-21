from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .narrative_verifier_service import NarrativeVerifierService


@dataclass
class NovelBenchCase:
    case_id: str
    project_id: str
    chapter_number: int
    target_min_chars: int
    target_max_chars: int
    must_include: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class NovelBenchLiteService:
    """Small deterministic evaluator for generation-regression snapshots."""

    def __init__(self, verifier: NarrativeVerifierService | None = None):
        self.verifier = verifier or NarrativeVerifierService()

    def evaluate_case(
        self,
        *,
        case: NovelBenchCase,
        chapter_text: str,
        plan: Any,
        evidence_summary: Dict[str, Any],
        review_summaries: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        text = chapter_text or ""
        verification = self.verifier.verify(
            plan=plan,
            chapter_text=text,
            review_summaries=review_summaries or {},
            evidence_summary=evidence_summary,
        )
        missing_terms = [term for term in case.must_include if term and term not in text]
        length_status = (
            "passed"
            if case.target_min_chars <= len(text) <= case.target_max_chars
            else "failed"
        )
        failed_verifications = verification["status_counts"].get("failed", 0)
        score = 100
        if length_status == "failed":
            score -= 20
        score -= min(30, len(missing_terms) * 10)
        score -= min(40, failed_verifications * 15)
        return {
            "case_id": case.case_id,
            "status": "passed" if score >= 70 and not missing_terms and length_status == "passed" else "failed",
            "score": max(0, score),
            "length": len(text),
            "length_status": length_status,
            "missing_terms": missing_terms,
            "verification": verification,
        }
