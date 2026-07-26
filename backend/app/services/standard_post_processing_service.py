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
                # 先跑免费规则修复再重扫，仍低于阈值才动用 LLM——对齐 fast/literary 的
                # scan→fix→rescan 模式（此前 standard 扫完直接 LLM，白烧一次调用）。
                # consistency 可能已改动正文，apply_rule_fixes 不传 report 使其基于最新正文重扫。
                try:
                    humanized = False
                    best_content = h_service.apply_rule_fixes(best_content)
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
                except Exception as exc:
                    logger.warning("人味化检查失败（不影响生成）: %s", exc)
                    review_summaries["humanization"] = {"error": str(exc)}
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
                    # 先跑免费规则修复再重扫，仍低于阈值才动用 LLM——对齐 fast/literary 的
                    # scan→fix→rescan 模式
                    h_report = h_service.scan(best_content)
                    best_content = h_service.apply_rule_fixes(best_content, h_report)
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
        # 每个可选 LLM 步执行前各自复检预算：前一步耗时可能已把剩余预算吃穿，
        # 只在四步连跑前查一次会让后续步骤在预算耗尽后仍然启动。
        if optimizer_enabled:
            if _over_budget():
                skipped_for_budget.append("optimizer")
                optimizer_enabled = False
                # optimizer 被预算跳过时，已付费勾选的润色降级为独立 polish 步执行（付费必交付）
                if config.enable_polish:
                    polish_only = True
            else:
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
            # 付费必交付：enable_polish 只可能来自用户勾选（preset 不再强开），
            # 已按 credits.price.polish 先扣费，不允许被时间预算跳过
            best_content, polish_report = await orchestrator._run_polish(
                best_content,
                user_id=user_id,
                max_word_count=chapter_word_count_max,
            )
            review_summaries["polish"] = polish_report

        if enrichment_enabled:
            if _over_budget():
                skipped_for_budget.append("enrichment")
            else:
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
            if _over_budget():
                skipped_for_budget.append("density_compression")
            else:
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

                if six_dim_result.get("degraded"):
                    # 审查降级（提示词缺失/解析失败兜底）：分数不可信，不触发重写也不伪装通过
                    review_summaries["enhanced_review"] = {"status": "degraded"}
                else:
                    overall_score = six_dim_result.get("overall_score", 0)
                    review_summaries["enhanced_review"] = {
                        "status": "completed",
                        "score": overall_score,
                    }
                    min_score_threshold = config.six_dimension_min_score
                    if overall_score < min_score_threshold:
                        # 反馈按提示词真实输出结构提取：summary 为总评，
                        # 各维度 issues 里的重度问题拼成缺陷清单
                        suggestions = six_dim_result.get("summary", "")
                        critical_flaws = []
                        for dim, analysis in six_dim_result.get("dimensions", {}).items():
                            if not isinstance(analysis, dict):
                                continue
                            for issue in analysis.get("issues") or []:
                                if not isinstance(issue, dict):
                                    continue
                                if issue.get("severity") not in ("critical", "major"):
                                    continue
                                parts = [
                                    part
                                    for part in (issue.get("description", ""), issue.get("suggestion", ""))
                                    if part
                                ]
                                if parts:
                                    critical_flaws.append(f"[{dim}缺陷]: " + "；".join(parts))
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
                                refiner_summary: Dict[str, Any] = {
                                    "triggered": True,
                                    "original_score": overall_score,
                                    "flaws_fixed": len(critical_flaws),
                                }
                                # refine 后重打分回退：重写可能反而变差，追加一次六维重打分，
                                # 新分低于原分则回退 refine 前文本（仅 refine 实际触发时 +1 次评审调用）。
                                if _over_budget():
                                    # 超预算：跳过重打分直接保留 refine 结果
                                    best_content = refined_content
                                    refiner_summary["rescore"] = "skipped_for_budget"
                                else:
                                    new_score = None
                                    try:
                                        rescore_result = await six_dim_service.review_chapter(
                                            project_id=project_id,
                                            chapter_number=chapter_number,
                                            chapter_title=outline_title,
                                            chapter_content=refined_content,
                                            user_id=user_id,
                                            chapter_plan=json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                                            previous_summary=history_context["previous_summary"],
                                        )
                                        if rescore_result and not rescore_result.get("degraded"):
                                            new_score = rescore_result.get("overall_score", 0)
                                    except Exception as rescore_exc:
                                        logger.warning("refine 后六维重打分失败，保留 refine 结果: %s", rescore_exc)
                                    if new_score is None:
                                        # 重打分降级/失败：分数不可信，保留 refine 结果（降级安全）
                                        best_content = refined_content
                                        refiner_summary["rescore"] = "degraded"
                                    elif new_score < overall_score:
                                        # 重写反而降分：回退 refine 前文本（best_content 保持不变）
                                        refiner_summary["reverted"] = True
                                        refiner_summary["new_score"] = new_score
                                    else:
                                        best_content = refined_content
                                        refiner_summary["new_score"] = new_score
                                review_summaries["auto_refiner"] = refiner_summary
            except Exception as exc:
                logger.warning("同步六维打分/重写失败，跳过拦截: %s", exc)
                review_summaries["enhanced_review"] = {"status": "degraded", "error": str(exc)}

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
