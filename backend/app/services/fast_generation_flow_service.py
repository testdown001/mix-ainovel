# AIMETA P=快速生成流程服务_单版本极速链路|R=快速正文生成_轻量后处理|NR=不含主流程编排|E=FastGenerationFlowService|X=internal|A=快速生成|D=asyncio|S=db,compute|RD=./README.ai
from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from ..db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class FastGenerationFlowResult:
    version: Dict[str, Any]
    best_content: str
    review_summaries: Dict[str, Any]
    stage_b_params: Dict[str, Any]


class FastGenerationFlowService:
    """封装 fast 单版本生成与本地后处理链路。"""

    def __init__(
        self,
        *,
        session,
        llm_service,
        single_version_generation_service,
        text_compression_service,
    ):
        self.session = session
        self.llm_service = llm_service
        self.single_version_generation_service = single_version_generation_service
        self.text_compression_service = text_compression_service

    async def run(
        self,
        *,
        prompt_input: str,
        writer_prompt: str,
        project_id: str,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        chapter_mission: Optional[dict],
        forbidden_characters: list[str],
        allowed_new_characters: list[str],
        user_id: int,
        writer_blueprint: Dict[str, Any],
        memory_context: Optional[str],
        enhanced_context: Dict[str, Any],
        config: Any,
        chapter_target_word_count: int,
        chapter_word_count_max: int,
        genre_profile: Optional[Dict[str, Any]],
        history_context: Dict[str, Any],
        emit_text_delta: Optional[Callable[[str], Awaitable[None]]] = None,
        mark_stage: Optional[Callable[[str, float], None]] = None,
        run_polish: Optional[Callable[..., Awaitable[tuple[str, Dict[str, Any]]]]] = None,
    ) -> FastGenerationFlowResult:
        stage_started = time.perf_counter()
        version = await self.single_version_generation_service.generate(
            index=0,
            prompt_input=prompt_input,
            writer_prompt=writer_prompt,
            style_hint=None,
            project_id=project_id,
            chapter_number=chapter_number,
            outline_title=outline_title,
            outline_summary=outline_summary,
            chapter_mission=chapter_mission,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            user_id=user_id,
            writer_blueprint=writer_blueprint,
            memory_context=memory_context,
            enhanced_context=enhanced_context,
            config=config,
            target_word_count=chapter_target_word_count,
            max_word_count=chapter_word_count_max,
            genre_profile=genre_profile,
            disable_guardrail_rewrite=config.disable_guardrail_rewrite,
            stream_callback=emit_text_delta,
        )
        if mark_stage:
            mark_stage("generate_fast_version", stage_started)

        best_content = version.get("content", "")
        review_summaries: Dict[str, Any] = {}

        if config.enable_lightweight_humanization:
            stage_started = time.perf_counter()
            try:
                from .humanization_service import HumanizationService

                humanization_service = HumanizationService(self.session, self.llm_service)
                report = humanization_service.scan(best_content)
                best_content = humanization_service.apply_rule_fixes(best_content, report)
                review_summaries["lightweight_humanization"] = {
                    "score": report.score,
                    "issues_count": len(report.issues),
                }
            except Exception as exc:
                logger.warning("Fast 规则人味化失败（不影响生成）: %s", exc)
                review_summaries["lightweight_humanization"] = {"error": str(exc)}
            if mark_stage:
                mark_stage("fast_lightweight_humanization", stage_started)

        if config.enable_polish and run_polish is not None:
            stage_started = time.perf_counter()
            best_content, polish_report = await run_polish(
                best_content,
                user_id=user_id,
                max_word_count=chapter_word_count_max,
            )
            review_summaries["polish"] = polish_report
            if mark_stage:
                mark_stage("fast_optional_polish", stage_started)

        if len(best_content) > chapter_word_count_max:
            logger.info(
                "Fast模式最终字数超限 (%d > %d)，触发兜底压缩",
                len(best_content),
                chapter_word_count_max,
            )
            best_content = await self.text_compression_service.compress_overlength(
                best_content,
                target_max=chapter_word_count_max,
                user_id=user_id,
            )
        if len(best_content) > chapter_word_count_max:
            logger.warning("Fast压缩后仍超限 (%d > %d)，触发硬截断", len(best_content), chapter_word_count_max)
            best_content = self.text_compression_service.hard_trim_to_limit(best_content, chapter_word_count_max)

        if config.enable_anti_hallucination:
            try:
                async with AsyncSessionLocal() as bg_session:
                    from .entity_registry_service import EntityRegistryService

                    entity_service = EntityRegistryService(bg_session)
                    alias_map = await entity_service.build_alias_map(project_id)
                    if alias_map:
                        for alias, canonical in alias_map.items():
                            if alias != canonical and alias in best_content:
                                best_content = best_content.replace(alias, canonical)
                                logger.info("Fast实体别名替换: %s -> %s", alias, canonical)
            except Exception as exc:
                logger.warning("Fast实体别名替换失败（不影响生成）: %s", exc)

        version["content"] = best_content
        review_summaries["quality_detection"] = {"status": "scheduled_async"}
        if config.enable_anti_hallucination:
            review_summaries["anti_hallucination"] = {
                "status": "scheduled_async",
                "mode": "local_registry" if config.use_local_anti_hallucination else "llm",
            }
        version.setdefault("metadata", {})["review_summaries"] = review_summaries

        stage_b_params = {
            "analysis_snapshot": best_content,
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chapter_mission": chapter_mission,
            "previous_summary": history_context["previous_summary"],
            "completed_chapters": history_context.get("completed_chapters", []),
            "enable_reader_sim": False,
            "enable_anti_hallucination": config.enable_anti_hallucination,
            "anti_hallucination_local_only": config.use_local_anti_hallucination,
            "user_id": user_id,
        }

        return FastGenerationFlowResult(
            version=version,
            best_content=best_content,
            review_summaries=review_summaries,
            stage_b_params=stage_b_params,
        )
