# AIMETA P=文学生成流程服务_场景写作与雕塑后处理|R=文学分支执行|NR=不含持久化与统一收尾|E=LiteraryGenerationFlowService|X=internal|A=文学生成|D=asyncio|S=db,compute|RD=./README.ai
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from ..db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class LiteraryGenerationFlowResult:
    version: Dict[str, Any]
    best_content: str
    review_summaries: Dict[str, Any]
    six_dimension_payload: Optional[Dict[str, Any]]
    voice_samples_text: str


class LiteraryGenerationFlowService:
    """封装文学模式的生成与后处理执行链。"""

    def __init__(
        self,
        *,
        session,
        llm_service,
        scene_generation_service,
        generation_policy_service,
        text_compression_service,
        guardrails,
    ):
        self.session = session
        self.llm_service = llm_service
        self.scene_generation_service = scene_generation_service
        self.generation_policy_service = generation_policy_service
        self.text_compression_service = text_compression_service
        self.guardrails = guardrails

    async def run(
        self,
        *,
        voice_samples_task: Optional[Any],
        context_plan: Any,
        prompt_compiler,
        prompt_sections_data: Dict[str, Any],
        writer_prompt: str,
        chapter_mission: Optional[dict],
        forbidden_characters: list[str],
        allowed_new_characters: list[str],
        user_id: int,
        genre_profile: Optional[Dict[str, Any]],
        chapter_word_count_max: int,
        chapter_target_word_count: int,
        chapter_word_count_min: int,
        config: Any,
        outline_title: str,
        history_context: Dict[str, Any],
        project_id: str,
        chapter_number: int,
        enhanced_context: Dict[str, Any],
        run_enrichment: Callable[..., Awaitable[tuple[str, Optional[Dict[str, Any]]]]],
        run_quality_detection: Callable[..., Awaitable[Dict[str, Any]]],
        mark_stage: Optional[Callable[[str, float], None]] = None,
        deadline: Optional[float] = None,
    ) -> LiteraryGenerationFlowResult:
        voice_samples_text = ""
        if voice_samples_task is not None:
            voice_samples_text = await voice_samples_task

        prompt_sections_data = dict(prompt_sections_data)
        prompt_sections_data["voice_samples"] = voice_samples_text
        prompt_sections_data = prompt_compiler.compile_scene_prompt_data(
            plan=context_plan,
            prompt_sections_data=prompt_sections_data,
        )

        stage_started = time.perf_counter()
        version = await self.scene_generation_service.generate_scene_by_scene(
            prompt_sections_data=prompt_sections_data,
            writer_prompt=writer_prompt,
            chapter_mission=chapter_mission,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            user_id=user_id,
            genre_profile=genre_profile,
            voice_samples_text=voice_samples_text,
            max_word_count=chapter_word_count_max,
            model_code=getattr(config, "model_code", None),
        )
        if mark_stage:
            mark_stage("generate_scene_by_scene", stage_started)

        stage_started = time.perf_counter()
        best_content = version["content"]
        review_summaries: Dict[str, Any] = {}

        # 关键路径软预算（与 standard_post_processing._over_budget 同一模式）：deadline 为
        # perf_counter 时间戳（None=不限）。每个可选后处理步启动前查剩余预算，不足单步预留
        # (180s) 即跳过并记录；场景生成本体不受预算约束（正文优先），只裁后处理。
        skipped_for_budget: list[str] = []
        _PER_STEP_RESERVE_SEC = 180.0

        def _over_budget() -> bool:
            return deadline is not None and (deadline - time.perf_counter()) < _PER_STEP_RESERVE_SEC

        literary_profile = self.generation_policy_service.resolve_literary_postprocess_profile(
            config=config,
            chapter_mission=chapter_mission,
            target_word_count=chapter_target_word_count,
        )
        review_summaries["literary_profile"] = literary_profile

        if literary_profile["enable_prose_sculpting"]:
            if _over_budget():
                skipped_for_budget.append("prose_sculpting")
            else:
                from .prose_sculptor_service import ProseSculptorService

                sculptor = ProseSculptorService(self.llm_service)
                best_content, rhythm_report = await sculptor.sculpt_rhythm(
                    best_content,
                    user_id=user_id,
                    max_word_count=chapter_word_count_max,
                )
                review_summaries["rhythm_sculpting"] = rhythm_report

                # rhythm 与 density 是两次独立 LLM 调用：一次检查连跑两步会冲破
                # 单步 180s 预留的预算不变量（正是该机制要防的 600s 硬超时复发）
                if _over_budget():
                    skipped_for_budget.append("density_sculpting")
                else:
                    best_content, density_report = await sculptor.sculpt_density(
                        best_content,
                        user_id=user_id,
                        max_word_count=chapter_word_count_max,
                    )
                    review_summaries["density_sculpting"] = density_report

        if literary_profile["enable_golden_paragraph"]:
            if _over_budget():
                skipped_for_budget.append("golden_paragraph")
            else:
                from .prose_sculptor_service import ProseSculptorService

                sculptor = ProseSculptorService(self.llm_service)
                best_content, golden_report = await sculptor.enhance_peak_moments(
                    best_content,
                    user_id=user_id,
                    chapter_mission=chapter_mission,
                )
                review_summaries["golden_paragraph"] = golden_report

        if literary_profile["enable_humanization"] and _over_budget():
            skipped_for_budget.append("humanization")
        elif literary_profile["enable_humanization"]:
            try:
                from .humanization_service import HumanizationService

                humanization_service = HumanizationService(self.session, self.llm_service)
                report = humanization_service.scan(best_content)
                best_content = humanization_service.apply_rule_fixes(best_content, report)
                report = humanization_service.scan(best_content)
                humanized = False
                if report.score < config.humanization_threshold:
                    best_content = await humanization_service.humanize(
                        best_content,
                        report,
                        user_id=user_id,
                    )
                    humanized = True
                review_summaries["humanization"] = {
                    "score": report.score,
                    "issues_count": len(report.issues),
                    "humanized": humanized,
                }
            except Exception as exc:
                logger.warning("人味化检查失败: %s", exc)

        if _over_budget():
            skipped_for_budget.append("enrichment")
        else:
            best_content, enrichment_report = await run_enrichment(
                best_content,
                user_id=user_id,
                target_word_count=chapter_target_word_count,
                min_word_count=chapter_word_count_min,
                max_word_count=chapter_word_count_max,
            )
            if enrichment_report:
                review_summaries["enrichment"] = enrichment_report

        guardrail_result = self.guardrails.check(
            generated_text=best_content,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            pov=chapter_mission.get("pov") if chapter_mission else None,
        )
        if not guardrail_result.passed:
            best_content = self.guardrails.apply_local_patches(best_content, guardrail_result)

        if mark_stage:
            mark_stage("literary_post_processing", stage_started)

        recent_openings = [
            chapter["summary"][:200]
            for chapter in history_context.get("completed_chapters", [])
            if chapter.get("summary")
        ][-3:]
        stage_started = time.perf_counter()
        if _over_budget():
            skipped_for_budget.append("quality_detection")
        else:
            quality_report = await run_quality_detection(
                best_content,
                chapter_number=chapter_number,
                chapter_mission=chapter_mission,
                previous_chapters_openings=recent_openings,
                user_id=user_id,
            )
            review_summaries["quality_detection"] = quality_report
        if mark_stage:
            mark_stage("literary_readonly_analyses", stage_started)

        if len(best_content) > chapter_word_count_max:
            logger.info(
                "Literary最终字数超限 (%d > %d)，触发兜底压缩",
                len(best_content),
                chapter_word_count_max,
            )
            best_content = await self.text_compression_service.compress_overlength(
                best_content,
                target_max=chapter_word_count_max,
                user_id=user_id,
            )
        if len(best_content) > chapter_word_count_max:
            logger.warning("Literary压缩后仍超限 (%d > %d)，触发硬截断", len(best_content), chapter_word_count_max)
            best_content = self.text_compression_service.hard_trim_to_limit(best_content, chapter_word_count_max)

        if config.enable_anti_hallucination:
            try:
                async with AsyncSessionLocal() as bg_session:
                    from .entity_registry_service import EntityRegistryService

                    entity_service = EntityRegistryService(bg_session)
                    alias_map = await entity_service.build_alias_map(project_id)
                    if alias_map:
                        best_content = EntityRegistryService.apply_alias_replacements(
                            best_content, alias_map, log_prefix="Literary实体别名替换",
                        )
            except Exception as exc:
                logger.warning("Literary实体别名替换失败（不影响生成）: %s", exc)

        if skipped_for_budget:
            logger.warning(
                "Literary 生成超时间预算，已跳过后处理步骤以保证按时返回(避免 600s 硬超时): %s",
                skipped_for_budget,
            )
            review_summaries["time_budget"] = {"exceeded": True, "skipped": skipped_for_budget}

        version["content"] = best_content
        version.setdefault("metadata", {})["review_summaries"] = review_summaries

        six_dimension_payload = None
        if enhanced_context and config.enable_six_dimension:
            six_dimension_payload = {
                "project_id": project_id,
                "chapter_number": chapter_number,
                "chapter_title": outline_title,
                "chapter_content": best_content,
                "chapter_plan": json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                "previous_summary": history_context["previous_summary"],
            }

        return LiteraryGenerationFlowResult(
            version=version,
            best_content=best_content,
            review_summaries=review_summaries,
            six_dimension_payload=six_dimension_payload,
            voice_samples_text=voice_samples_text,
        )
