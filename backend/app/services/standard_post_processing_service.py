from __future__ import annotations

import json
import logging
import asyncio
import time
from typing import Any, Dict, Optional

from .writer_shared import rewrite_with_guardrails as _shared_rewrite_with_guardrails

logger = logging.getLogger(__name__)


class StandardPostProcessingService:
    """封装标准模式下的后处理阶段执行。"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def run(
        self,
        *,
        best_content: str,
        best_version: Dict[str, Any],
        ai_review_result: Optional[Dict[str, Any]],
        review_summaries: Dict[str, Any],
        config: Any,
        project_id: str,
        chapter_number: int,
        chapter_mission: Optional[dict],
        writer_blueprint: Dict[str, Any],
        history_context: Dict[str, Any],
        user_id: int,
        chapter_word_count_min: int,
        chapter_word_count_max: int,
        chapter_target_word_count: int,
        enhanced_flow: Any,
        outline_title: str,
        forbidden_characters: list[str],
        allowed_new_characters: list[str],
        deadline: Optional[float] = None,
    ) -> Dict[str, Any]:
        orchestrator = self.orchestrator
        stage_timings_ms: Dict[str, int] = {}

        # 关键路径软预算：deadline 为 perf_counter 时间戳（None=不限）。每个可选后处理步骤
        # 前检查，预算不足即跳过该步及后续可选步骤，带"当前最佳稿"继续，避免拖到硬超时全盘失败。
        # 关键：单个后处理 LLM 步最坏约 180s，必须"剩余预算够再跑一整步"才启动，否则末步在
        # deadline 前一刻启动却跑满 180s，会冲破 600s 前端/网关硬超时致全盘失败(上版缺陷)。
        skipped_for_budget: list[str] = []
        _PER_STEP_RESERVE_SEC = 180.0

        def _over_budget() -> bool:
            return deadline is not None and (deadline - time.perf_counter()) < _PER_STEP_RESERVE_SEC

        has_review_feedback = bool(ai_review_result and (ai_review_result.get("flaws") or ai_review_result.get("suggestions")))
        if has_review_feedback or config.enable_self_critique:
            if _over_budget():
                skipped_for_budget.append("combined_revision")
            else:
                best_content, combined_report = await orchestrator._run_combined_revision(
                    best_content,
                    critical_flaws=(ai_review_result.get("flaws") or []) if ai_review_result else [],
                    refinement_suggestions=(ai_review_result.get("suggestions") or "") if ai_review_result else "",
                    enable_self_critique=config.enable_self_critique,
                    chapter_mission=chapter_mission,
                    user_id=user_id,
                    context={
                        "character_profiles": json.dumps(writer_blueprint.get("characters", []), ensure_ascii=False),
                        "previous_summary": history_context["previous_summary"],
                    },
                    max_word_count=chapter_word_count_max,
                )
                review_summaries["combined_revision"] = combined_report

        consistency_enabled = config.enable_consistency
        humanization_enabled = config.enable_humanization
        if (consistency_enabled or humanization_enabled) and _over_budget():
            if consistency_enabled:
                skipped_for_budget.append("consistency")
            if humanization_enabled:
                skipped_for_budget.append("humanization")
        elif consistency_enabled and humanization_enabled:
            async def _do_consistency():
                return await orchestrator._run_consistency_check(
                    project_id=project_id,
                    chapter_text=best_content,
                    user_id=user_id,
                )

            async def _do_humanization_scan():
                try:
                    from .humanization_service import HumanizationService
                    h_service = HumanizationService(orchestrator.session, orchestrator.llm_service)
                    return h_service, h_service.scan(best_content)
                except Exception as exc:
                    logger.warning("人味化扫描失败（不影响生成）: %s", exc)
                    return None, None

            (consistency_content, consistency_report), (h_service, h_report) = await asyncio.gather(
                _do_consistency(),
                _do_humanization_scan(),
            )
            best_content = consistency_content
            review_summaries["consistency"] = consistency_report

            if h_service and h_report:
                humanized = False
                if h_report.score < config.humanization_threshold:
                    h_report = h_service.scan(best_content)
                    if h_report.score < config.humanization_threshold:
                        best_content = await h_service.humanize(best_content, h_report, user_id=user_id)
                        humanized = True
                review_summaries["humanization"] = {
                    "score": h_report.score,
                    "issues_count": len(h_report.issues),
                    "humanized": humanized,
                    "details": h_report.to_dict(),
                }
        else:
            if consistency_enabled:
                best_content, consistency_report = await orchestrator._run_consistency_check(
                    project_id=project_id,
                    chapter_text=best_content,
                    user_id=user_id,
                )
                review_summaries["consistency"] = consistency_report

            if humanization_enabled:
                try:
                    from .humanization_service import HumanizationService
                    h_service = HumanizationService(orchestrator.session, orchestrator.llm_service)
                    h_report = h_service.scan(best_content)
                    humanized = False
                    if h_report.score < config.humanization_threshold:
                        best_content = await h_service.humanize(best_content, h_report, user_id=user_id)
                        humanized = True
                    review_summaries["humanization"] = {
                        "score": h_report.score,
                        "issues_count": len(h_report.issues),
                        "humanized": humanized,
                        "details": h_report.to_dict(),
                    }
                except Exception as exc:
                    logger.warning("人味化检查失败（不影响生成）: %s", exc)
                    review_summaries["humanization"] = {"error": str(exc)}

        analysis_snapshot = best_content
        stage_b_params = {
            "analysis_snapshot": analysis_snapshot,
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chapter_mission": chapter_mission,
            "previous_summary": history_context["previous_summary"],
            "completed_chapters": history_context.get("completed_chapters", []),
            "enable_reader_sim": config.enable_reader_sim,
            "enable_anti_hallucination": config.enable_anti_hallucination,
            "anti_hallucination_local_only": config.use_local_anti_hallucination,
            "user_id": user_id,
        }
        if config.enable_reader_sim:
            review_summaries["reader_simulator"] = {"status": "scheduled_async"}
        if config.enable_anti_hallucination:
            review_summaries["anti_hallucination"] = {"status": "scheduled_async"}
        review_summaries["quality_detection"] = {"status": "scheduled_async"}

        optimizer_enabled = config.enable_optimizer
        enrichment_enabled = config.enable_enrichment and not optimizer_enabled
        polish_only = config.enable_polish and not optimizer_enabled
        density_enabled = config.enable_density_compression
        if _over_budget():
            if optimizer_enabled:
                skipped_for_budget.append("optimizer")
            if polish_only:
                skipped_for_budget.append("polish")
            if enrichment_enabled:
                skipped_for_budget.append("enrichment")
            if density_enabled:
                skipped_for_budget.append("density_compression")
            optimizer_enabled = enrichment_enabled = polish_only = density_enabled = False
        if optimizer_enabled:
            merge_polish = config.enable_polish
            merge_density = (
                config.enable_density_compression
                and chapter_word_count_max
                and len(best_content) >= chapter_word_count_max * 0.90
            )
            best_content, optimizer_report = await orchestrator._run_optimizer(
                best_content,
                user_id=user_id,
                include_polish=merge_polish,
                include_density=merge_density,
                max_word_count=chapter_word_count_max,
            )
            review_summaries["optimizer"] = optimizer_report
            if merge_polish:
                review_summaries["polish"] = {"applied": True, "merged_into_optimizer": True}
            if merge_density:
                review_summaries["density_compression"] = {"applied": True, "merged_into_optimizer": True}

        if polish_only:
            best_content, polish_report = await orchestrator._run_polish(
                best_content,
                user_id=user_id,
                max_word_count=chapter_word_count_max,
            )
            review_summaries["polish"] = polish_report

        if enrichment_enabled:
            best_content, enrichment_report = await orchestrator._run_enrichment(
                best_content,
                user_id=user_id,
                target_word_count=chapter_target_word_count,
                min_word_count=chapter_word_count_min,
                max_word_count=chapter_word_count_max,
            )
            if enrichment_report:
                review_summaries["enrichment"] = enrichment_report

        if density_enabled and not (
            optimizer_enabled and review_summaries.get("density_compression", {}).get("merged_into_optimizer")
        ):
            current_len = len(best_content)
            if chapter_word_count_max and current_len < chapter_word_count_max * 0.90:
                review_summaries["density_compression"] = {"applied": False, "reason": "below_90pct_max"}
            else:
                best_content, density_report = await orchestrator._run_density_compression(
                    best_content,
                    user_id=user_id,
                    max_word_count=chapter_word_count_max,
                )
                review_summaries["density_compression"] = density_report

        if enhanced_flow and config.enable_six_dimension and _over_budget():
            skipped_for_budget.append("six_dimension")
            review_summaries["enhanced_review"] = {"status": "skipped_for_budget"}
        if enhanced_flow and config.enable_six_dimension and not _over_budget():
            from ..services.six_dimension_review_service import SixDimensionReviewService
            from ..services.constitution_service import ConstitutionService
            from ..services.writer_persona_service import WriterPersonaService

            constitution_service = ConstitutionService(orchestrator.session, orchestrator.llm_service, orchestrator.prompt_service)
            writer_persona_service = WriterPersonaService(orchestrator.session, orchestrator.llm_service, orchestrator.prompt_service)
            six_dim_service = SixDimensionReviewService(
                orchestrator.session,
                orchestrator.llm_service,
                orchestrator.prompt_service,
                constitution_service,
                writer_persona_service,
            )
            try:
                six_dim_result = await six_dim_service.review_chapter(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_title=outline_title,
                    chapter_content=best_content,
                    user_id=user_id,
                    chapter_plan=json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                    previous_summary=history_context["previous_summary"],
                )

                review_summaries["enhanced_review"] = {
                    "status": "completed",
                    "score": six_dim_result.get("overall_score", 0),
                }
                min_score_threshold = getattr(config, "six_dimension_min_score", 70)
                overall_score = six_dim_result.get("overall_score", 0)
                if overall_score < min_score_threshold:
                    critical_flaws = []
                    suggestions = six_dim_result.get("overall_review", "")
                    for dim, analysis in six_dim_result.get("dimensions", {}).items():
                        if analysis.get("score", 100) < min_score_threshold:
                            fault = analysis.get("analysis", "")
                            if fault:
                                critical_flaws.append(f"[{dim}缺陷]: {fault}")
                    if critical_flaws or suggestions:
                        refined_content, revision_meta = await orchestrator._run_combined_revision(
                            chapter_content=best_content,
                            critical_flaws=critical_flaws,
                            refinement_suggestions=suggestions,
                            enable_self_critique=False,
                            chapter_mission=chapter_mission,
                            user_id=user_id,
                            context=history_context,
                            max_word_count=chapter_word_count_max,
                        )
                        if revision_meta.get("applied"):
                            best_content = refined_content
                            review_summaries["auto_refiner"] = {
                                "triggered": True,
                                "original_score": overall_score,
                                "flaws_fixed": len(critical_flaws),
                            }
            except Exception as exc:
                logger.warning("同步六维打分/重写失败，跳过拦截: %s", exc)

        best_guardrail_meta = best_version.get("metadata", {}).get("guardrail", {})
        if best_guardrail_meta.get("deferred_llm_rewrite"):
            final_guardrail = orchestrator.guardrails.check(
                generated_text=best_content,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                pov=chapter_mission.get("pov") if chapter_mission else None,
            )
            if not final_guardrail.passed:
                best_content = orchestrator.guardrails.apply_local_patches(best_content, final_guardrail)
                recheck = orchestrator.guardrails.check(
                    generated_text=best_content,
                    forbidden_characters=forbidden_characters,
                    allowed_new_characters=allowed_new_characters,
                    pov=chapter_mission.get("pov") if chapter_mission else None,
                )
                if not recheck.passed and not _over_budget():
                    violations_text = orchestrator.guardrails.format_violations_for_rewrite(recheck)
                    best_content = await _shared_rewrite_with_guardrails(
                        orchestrator.llm_service,
                        orchestrator.prompt_service,
                        original_text=best_content,
                        chapter_mission=chapter_mission,
                        violations_text=violations_text,
                        user_id=user_id,
                    )
                elif not recheck.passed:
                    # 越预算：保留已应用的本地补丁，跳过慢的 LLM 重写
                    skipped_for_budget.append("guardrail_rewrite")
                best_guardrail_meta["final_guardrail_applied"] = True
            else:
                best_guardrail_meta["deferred_llm_rewrite"] = False
                best_guardrail_meta["resolved_by_postprocess"] = True

        if skipped_for_budget:
            logger.warning(
                "生成超时间预算，已跳过后处理步骤以保证按时返回(避免 600s 硬超时): %s",
                skipped_for_budget,
            )
            review_summaries["time_budget"] = {"exceeded": True, "skipped": skipped_for_budget}

        best_version["content"] = best_content
        best_version.setdefault("metadata", {})["review_summaries"] = review_summaries

        return {
            "best_content": best_content,
            "review_summaries": review_summaries,
            "stage_b_params": stage_b_params,
            "stage_timings_ms": stage_timings_ms,
        }
