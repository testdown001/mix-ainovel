# AIMETA P=标准生成流程服务_多版本与StageA后处理|R=标准分支执行|NR=不含持久化与统一收尾|E=StandardGenerationFlowService|X=internal|A=标准生成|D=asyncio|S=db,compute|RD=./README.ai
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class StandardGenerationFlowResult:
    versions: List[Dict[str, Any]]
    best_version_index: int
    ai_review_result: Optional[Dict[str, Any]]
    best_content: str
    review_summaries: Dict[str, Any]
    stage_b_params: Optional[Dict[str, Any]]


class StandardGenerationFlowService:
    """封装标准多版本分支执行链。"""

    def __init__(
        self,
        *,
        session,
        llm_service,
        version_generation_service,
        standard_post_processing_service,
        text_compression_service,
    ):
        self.session = session
        self.llm_service = llm_service
        self.version_generation_service = version_generation_service
        self.standard_post_processing_service = standard_post_processing_service
        self.text_compression_service = text_compression_service

    async def run(
        self,
        *,
        prompt_input: str,
        prompt_sections: Optional[list] = None,
        writer_prompt: str,
        enhanced_context: Dict[str, Any],
        config: Any,
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
        chapter_target_word_count: int,
        chapter_word_count_min: int,
        chapter_word_count_max: int,
        genre_profile: Optional[Dict[str, Any]],
        history_context: Dict[str, Any],
        mark_stage: Optional[Callable[[str, float], None]] = None,
        deadline: Optional[float] = None,
    ) -> StandardGenerationFlowResult:
        version_count = config.version_count

        stage_started = time.perf_counter()
        generation_result = await self.version_generation_service.run(
            prompt_input=prompt_input,
            prompt_sections=prompt_sections,
            writer_prompt=writer_prompt,
            enhanced_context=enhanced_context,
            version_count=version_count,
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
            config=config,
            chapter_target_word_count=chapter_target_word_count,
            chapter_word_count_max=chapter_word_count_max,
            genre_profile=genre_profile,
        )
        if mark_stage:
            mark_stage("generate_versions", stage_started)

        versions = generation_result["versions"]

        stage_started = time.perf_counter()
        best_version_index = generation_result["best_version_index"]
        ai_review_result = generation_result["ai_review_result"]
        if mark_stage:
            mark_stage("ai_review", stage_started)

        review_summaries: Dict[str, Any] = {}
        stage_b_params: Optional[Dict[str, Any]] = None
        if ai_review_result:
            review_summaries["ai_review"] = ai_review_result

        best_content = ""
        if versions:
            best_version = versions[best_version_index]
            best_content = best_version["content"]
            stage_started = time.perf_counter()
            post_result = await self.standard_post_processing_service.run(
                best_content=best_content,
                best_version=best_version,
                ai_review_result=ai_review_result,
                review_summaries=review_summaries,
                config=config,
                project_id=project_id,
                chapter_number=chapter_number,
                chapter_mission=chapter_mission,
                writer_blueprint=writer_blueprint,
                history_context=history_context,
                user_id=user_id,
                chapter_word_count_min=chapter_word_count_min,
                chapter_word_count_max=chapter_word_count_max,
                chapter_target_word_count=chapter_target_word_count,
                enhanced_flow=bool(enhanced_context),
                outline_title=outline_title,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                deadline=deadline,
            )
            best_content = post_result["best_content"]
            review_summaries = post_result["review_summaries"]
            stage_b_params = post_result["stage_b_params"]
            if mark_stage:
                mark_stage("stage_a_post_processing", stage_started)

            if len(best_content) > chapter_word_count_max:
                logger.info("标准模式最终字数超限 (%d > %d)，触发兜底压缩", len(best_content), chapter_word_count_max)
                best_content = await self.text_compression_service.compress_overlength(
                    best_content,
                    target_max=chapter_word_count_max,
                    user_id=user_id,
                )
            if len(best_content) > chapter_word_count_max:
                logger.warning("标准模式压缩后仍超限 (%d > %d)，触发硬截断", len(best_content), chapter_word_count_max)
                best_content = self.text_compression_service.hard_trim_to_limit(best_content, chapter_word_count_max)

            if config.enable_anti_hallucination:
                try:
                    async with AsyncSessionLocal() as bg_session:
                        from .entity_registry_service import EntityRegistryService

                        entity_service = EntityRegistryService(bg_session)
                        alias_map = await entity_service.build_alias_map(project_id)
                        if alias_map:
                            best_content = EntityRegistryService.apply_alias_replacements(
                                best_content, alias_map, log_prefix="标准模式实体别名替换",
                            )
                except Exception as exc:
                    logger.warning("标准模式实体别名替换失败（不影响生成）: %s", exc)

            best_version["content"] = best_content

        return StandardGenerationFlowResult(
            versions=versions,
            best_version_index=best_version_index,
            ai_review_result=ai_review_result,
            best_content=best_content,
            review_summaries=review_summaries,
            stage_b_params=stage_b_params,
        )
