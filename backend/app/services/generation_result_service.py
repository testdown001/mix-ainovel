from __future__ import annotations

from typing import Any, Dict, List, Optional


class GenerationResultService:
    """统一装配生成结果、调试元数据与验证报告绑定。"""

    def attach_verification_report(
        self,
        *,
        verification_report: Dict[str, Any],
        versions: Optional[List[Dict[str, Any]]] = None,
        variants: Optional[List[Dict[str, Any]]] = None,
        best_version_index: int = 0,
    ) -> None:
        if versions and 0 <= best_version_index < len(versions):
            versions[best_version_index].setdefault("metadata", {})["verification_report"] = verification_report
        if variants and 0 <= best_version_index < len(variants):
            variants[best_version_index].setdefault("metadata", {})["verification_report"] = verification_report

    def build_debug_metadata(
        self,
        *,
        version_count: int,
        stage_flags: Dict[str, Any],
        rag_stats: Optional[Dict[str, Any]],
        context_plan: Dict[str, Any],
        retrieval_evidence_summary: Dict[str, Any],
        prompt_compile_summary: Dict[str, Any],
        verification_report: Dict[str, Any],
        stage_timings_ms: Dict[str, int],
        strategy_warnings: List[str],
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "version_count": version_count,
            "stages": stage_flags,
            "retrieval_stats": rag_stats,
            "context_plan": context_plan,
            "retrieval_evidence_summary": retrieval_evidence_summary,
            "prompt_compile_summary": prompt_compile_summary,
            "verification_report": verification_report,
            "stage_timings_ms": stage_timings_ms,
            "strategy_warnings": strategy_warnings,
        }
        if mode:
            payload["mode"] = mode
        return payload

    def build_response_payload(
        self,
        *,
        project_id: str,
        chapter_number: int,
        preset: str,
        best_version_index: int,
        variants: List[Dict[str, Any]],
        review_summaries: Dict[str, Any],
        debug_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "preset": preset,
            "best_version_index": best_version_index,
            "variants": variants,
            "review_summaries": review_summaries,
            "debug_metadata": debug_metadata,
        }
