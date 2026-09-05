from __future__ import annotations

import json
import logging
import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from .emotional_editing_service import preserve_passages
from .writer_shared import rewrite_with_guardrails as _shared_rewrite_with_guardrails

logger = logging.getLogger(__name__)

# 后处理各步的用户可读名。前端按 stage key 映射自己的文案，这里的中文是兜底：
# 老前端、批量任务日志、以及任何直接看 task 进度的地方都靠它。
POST_STAGE_LABELS: Dict[str, str] = {
    "post_combined_revision": "按评审意见修订",
    "post_consistency": "一致性校对",
    "post_humanization": "打磨行文",
    "post_optimizer": "精修文字",
    "post_polish": "润色",
    "post_enrichment": "补充细节",
    "post_density_compression": "压缩冗余",
    "post_six_dimension": "六维质量评审",
    "post_auto_refine": "按评分补写",
    "post_six_dimension_rescore": "复评",
    "post_guardrail_rewrite": "底线校验",
}


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
        mark_stage: Optional[Callable[[str, float], None]] = None,
        emit_stage: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        orchestrator = self.orchestrator
        stage_timings_ms: Dict[str, int] = {}
        protected_passages: list[dict] = []
        preservation_events: list[dict] = []

        def _accept_style(before: str, after: str, report: Optional[dict], stage: str):
            accepted, rejection = preserve_passages(before, after, protected_passages)
            if rejection:
                preservation_events.append({"stage": stage, **rejection})
                report = {**(report or {}), **rejection}
            return accepted, report

        # 分步计时：这条链是 6-10 次顺序 LLM 调用，此前整条只有外层一个
        # stage_a_post_processing span，耗时是一整块黑盒——要判断该优化哪一步，
        # 只能去 llm.log 里按时间戳手工对齐调用序列。每步各记一条：既填回
        # stage_timings_ms(此前声明了却从没写入过)，也发 span 进 trace.log，
        # 后台「生成诊断」因此能直接看到钱花在哪一步。
        def _step(name: str, started: float) -> None:
            stage_timings_ms[name] = int((time.perf_counter() - started) * 1000)
            if mark_stage:
                mark_stage(name, started)

        async def _begin(name: str) -> float:
            """开工一步：发阶段事件 + 返回计时起点。

            这条链占一章生成约四成时长，而在此之前它对前端**完全静默**——最后一条阶段
            事件停在「多版本生成中」，用户盯着不动的进度条看一分多钟，只能理解为卡死。
            事件必须在这一步开始时发（而不是结束时），否则显示的永远是上一步的名字。
            """
            if emit_stage:
                await emit_stage(name, POST_STAGE_LABELS.get(name, "精修中"))
            return time.perf_counter()

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
                _started = await _begin("post_combined_revision")
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
                protected_passages = [
                    p for p in (combined_report.get("emotional_review") or {}).get("protected_passages", [])
                    if p.get("quote") and p["quote"] in best_content
                ]
                _step("post_combined_revision", _started)

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

            _started = await _begin("post_consistency")
            (consistency_content, consistency_report), (h_service, h_report) = await asyncio.gather(
                _do_consistency(),
                _do_humanization_scan(),
            )
            best_content = consistency_content
            protected_passages = [p for p in protected_passages if p["quote"] in best_content]
            review_summaries["consistency"] = consistency_report
            # 并行段：人味化扫描是纯规则（无 LLM），耗时实际等于一致性检查那次调用
            _step("post_consistency", _started)

            if h_service and h_report:
                # 先跑免费规则修复再重扫，仍低于阈值才动用 LLM——对齐 fast/literary 的
                # scan→fix→rescan 模式（此前 standard 扫完直接 LLM，白烧一次调用）。
                # consistency 可能已改动正文，apply_rule_fixes 不传 report 使其基于最新正文重扫。
                try:
                    humanized = False
                    before_style = best_content
                    best_content = h_service.apply_rule_fixes(best_content)
                    best_content, _ = _accept_style(before_style, best_content, None, "humanization")
                    h_report = h_service.scan(best_content)
                    if h_report.score < config.humanization_threshold:
                        _started = await _begin("post_humanization")
                        before_style = best_content
                        best_content = await h_service.humanize(best_content, h_report, user_id=user_id,
                            **({"protected_passages": protected_passages} if protected_passages else {}))
                        best_content, _ = _accept_style(before_style, best_content, None, "humanization")
                        humanized = best_content != before_style
                        _step("post_humanization", _started)
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
                _started = await _begin("post_consistency")
                best_content, consistency_report = await orchestrator._run_consistency_check(
                    project_id=project_id,
                    chapter_text=best_content,
                    user_id=user_id,
                )
                review_summaries["consistency"] = consistency_report
                protected_passages = [p for p in protected_passages if p["quote"] in best_content]
                _step("post_consistency", _started)

            if humanization_enabled:
                try:
                    from .humanization_service import HumanizationService
                    h_service = HumanizationService(orchestrator.session, orchestrator.llm_service)
                    # 先跑免费规则修复再重扫，仍低于阈值才动用 LLM——对齐 fast/literary 的
                    # scan→fix→rescan 模式
                    h_report = h_service.scan(best_content)
                    before_style = best_content
                    best_content = h_service.apply_rule_fixes(best_content, h_report)
                    best_content, _ = _accept_style(before_style, best_content, None, "humanization")
                    h_report = h_service.scan(best_content)
                    humanized = False
                    if h_report.score < config.humanization_threshold:
                        _started = await _begin("post_humanization")
                        before_style = best_content
                        best_content = await h_service.humanize(best_content, h_report, user_id=user_id,
                            **({"protected_passages": protected_passages} if protected_passages else {}))
                        best_content, _ = _accept_style(before_style, best_content, None, "humanization")
                        humanized = best_content != before_style
                        _step("post_humanization", _started)
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
        # enrichment 与 optimizer 互斥：optimizer 本身是全篇改写增益，两步叠加是浪费。
        # 但互斥的前提是「optimizer 确实跑了且产出达标」——这个判断**不能在 optimizer
        # 跑之前一次算死**，否则出现两种漏网（下方两处复检各修其一）：
        #   1. optimizer 被预算跳过 → 互斥前提不成立，enrichment 却已被判 False 一起不跑；
        #   2. optimizer 跑完但产出偏短 → 无任何补救（density 只压不扩）。
        enrichment_enabled = config.enable_enrichment and not optimizer_enabled
        enrichment_trigger: Optional[str] = None  # 非空表示 enrichment 是被兜底逻辑触发的
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
                # 互斥前提（optimizer 会跑）已不成立，恢复 enrichment。
                # 若预算也不够，下方 enrichment 自己的 _over_budget 会拦并如实计入 skipped。
                enrichment_enabled = config.enable_enrichment
            else:
                merge_polish = config.enable_polish
                merge_density = (
                    config.enable_density_compression
                    and chapter_word_count_max
                    and len(best_content) >= chapter_word_count_max * 0.90
                )
                _started = await _begin("post_optimizer")
                before_style = best_content
                best_content, optimizer_report = await orchestrator._run_optimizer(
                    best_content,
                    user_id=user_id,
                    include_polish=merge_polish,
                    include_density=merge_density,
                    max_word_count=chapter_word_count_max,
                    **({"protected_passages": protected_passages} if protected_passages else {}),
                )
                best_content, optimizer_report = _accept_style(before_style, best_content, optimizer_report, "optimizer")
                review_summaries["optimizer"] = optimizer_report
                _step("post_optimizer", _started)
                # optimizer 失败会原样返回入参文本（applied=False），此时合并进去的润色/压缩
                # 同样一个字都没改。这里必须如实反映：润色是勾选计费项，报成 applied=True
                # 会让「未交付」看起来像已交付，用户的附加费就退不回去了。
                merged_applied = (optimizer_report or {}).get("applied") is not False
                if merge_polish:
                    review_summaries["polish"] = {
                        "applied": merged_applied,
                        "merged_into_optimizer": True,
                    }
                    if not merged_applied:
                        review_summaries["polish"]["reason"] = "optimizer_failed"
                if merge_density:
                    review_summaries["density_compression"] = {
                        "applied": merged_applied,
                        "merged_into_optimizer": True,
                    }
                # optimizer 跑完复检长度：它是「改写增益」不是「扩写」，产出低于下限时
                # 全流程再无补救（density 只压不扩）。此时解除互斥，让 enrichment 兜底。
                if (
                    config.enable_enrichment
                    and chapter_word_count_min
                    and len(best_content) < chapter_word_count_min
                ):
                    enrichment_enabled = True
                    enrichment_trigger = "below_min_after_optimizer"
                    logger.info(
                        "optimizer 产出低于字数下限(%d < %d)，启用 enrichment 兜底",
                        len(best_content), chapter_word_count_min,
                    )

        if polish_only:
            # 付费必交付：enable_polish 只可能来自用户勾选（preset 不再强开），
            # 已按 credits.price.polish 先扣费，不允许被时间预算跳过
            _started = await _begin("post_polish")
            before_style = best_content
            best_content, polish_report = await orchestrator._run_polish(
                best_content,
                user_id=user_id,
                max_word_count=chapter_word_count_max,
                **({"protected_passages": protected_passages} if protected_passages else {}),
            )
            best_content, polish_report = _accept_style(before_style, best_content, polish_report, "polish")
            review_summaries["polish"] = polish_report
            _step("post_polish", _started)

        if enrichment_enabled:
            if _over_budget():
                skipped_for_budget.append("enrichment")
            else:
                _started = await _begin("post_enrichment")
                before_style = best_content
                best_content, enrichment_report = await orchestrator._run_enrichment(
                    best_content,
                    user_id=user_id,
                    target_word_count=chapter_target_word_count,
                    min_word_count=chapter_word_count_min,
                    max_word_count=chapter_word_count_max,
                )
                best_content, enrichment_report = _accept_style(before_style, best_content, enrichment_report, "enrichment")
                _step("post_enrichment", _started)
                if enrichment_report:
                    if enrichment_trigger:
                        enrichment_report = {**enrichment_report, "trigger": enrichment_trigger}
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
                    _started = await _begin("post_density_compression")
                    before_style = best_content
                    best_content, density_report = await orchestrator._run_density_compression(
                        best_content,
                        user_id=user_id,
                        max_word_count=chapter_word_count_max,
                        **({"protected_passages": protected_passages} if protected_passages else {}),
                    )
                    best_content, density_report = _accept_style(before_style, best_content, density_report, "density_compression")
                    review_summaries["density_compression"] = density_report
                    _step("post_density_compression", _started)

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
                _started = await _begin("post_six_dimension")
                six_dim_result = await six_dim_service.review_chapter(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_title=outline_title,
                    chapter_content=best_content,
                    user_id=user_id,
                    chapter_plan=json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                    previous_summary=history_context["previous_summary"],
                )
                _step("post_six_dimension", _started)

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
                            _started = await _begin("post_auto_refine")
                            refined_content, revision_meta = await orchestrator._run_combined_revision(
                                chapter_content=best_content,
                                critical_flaws=critical_flaws,
                                refinement_suggestions=suggestions,
                                enable_self_critique=False,
                                chapter_mission=chapter_mission,
                                user_id=user_id,
                                context={**history_context, "protected_passages": protected_passages},
                                max_word_count=chapter_word_count_max,
                            )
                            refined_content, revision_meta = _accept_style(
                                best_content, refined_content, revision_meta, "auto_refine")
                            review_summaries["auto_refine_revision"] = revision_meta
                            _step("post_auto_refine", _started)
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
                                        _started = await _begin("post_six_dimension_rescore")
                                        rescore_result = await six_dim_service.review_chapter(
                                            project_id=project_id,
                                            chapter_number=chapter_number,
                                            chapter_title=outline_title,
                                            chapter_content=refined_content,
                                            user_id=user_id,
                                            chapter_plan=json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                                            previous_summary=history_context["previous_summary"],
                                        )
                                        _step("post_six_dimension_rescore", _started)
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
                    _started = await _begin("post_guardrail_rewrite")
                    best_content = await _shared_rewrite_with_guardrails(
                        orchestrator.llm_service,
                        orchestrator.prompt_service,
                        original_text=best_content,
                        chapter_mission=chapter_mission,
                        violations_text=violations_text,
                        user_id=user_id,
                    )
                    _step("post_guardrail_rewrite", _started)
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

        stage_b_params["analysis_snapshot"] = best_content
        if preservation_events:
            review_summaries["passage_preservation"] = {"events": preservation_events}
        best_version["content"] = best_content
        best_version.setdefault("metadata", {})["review_summaries"] = review_summaries

        return {
            "best_content": best_content,
            "review_summaries": review_summaries,
            "stage_b_params": stage_b_params,
            "stage_timings_ms": stage_timings_ms,
        }
