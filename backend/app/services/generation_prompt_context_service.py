# AIMETA P=生成提示上下文服务_任务书与节奏补全|R=Mission后上下文补全|NR=不含主流程编排|E=GenerationPromptContextService|X=internal|A=提示上下文|D=asyncio|S=compute,db|RD=./README.ai
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..core.config import settings
from .platinum_writing_context import (
    PLATINUM_WRITING_BRIEF_FALLBACK,
    build_hook_continuity_brief,
    build_platinum_rhythm_brief,
)

logger = logging.getLogger(__name__)


@dataclass
class PromptContextInputs:
    total_chapters: int
    platinum_writing_brief: str
    genre_profile: Optional[Dict[str, Any]]
    genre_prompt_injection: str
    genre_pacing_config: Optional[Dict[str, Any]]
    strand_info: Optional[Dict[str, Any]]
    platinum_rhythm_brief: str
    hook_continuity_brief: str
    emotion_expression_brief: str


class GenerationPromptContextService:
    """负责 Mission 后的提示上下文补全。"""

    def __init__(self, *, prompt_service, context_access_service, prompt_assembly_service):
        self.prompt_service = prompt_service
        self.context_access_service = context_access_service
        self.prompt_assembly_service = prompt_assembly_service

    async def get_memory_context_if_enabled(
        self,
        *,
        enabled: bool,
        project_id: str,
        chapter_number: int,
        introduced_characters: list[str],
    ) -> Optional[str]:
        if not enabled:
            return None
        return await self.context_access_service.get_memory_context(
            project_id=project_id,
            chapter_number=chapter_number,
            involved_characters=introduced_characters,
        )

    async def await_mission_brief(self, mission_brief_task: Optional[Any]) -> Optional[str]:
        if mission_brief_task is None:
            return None
        try:
            return await mission_brief_task
        except Exception as exc:
            logger.warning("Mission brief 生成失败（不影响生成）: %s", exc)
            return None

    async def resolve_prompt_context_inputs(
        self,
        *,
        config: Any,
        project: Any,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        chapter_mission: Optional[dict],
        history_context: Dict[str, Any],
        blueprint_dict: Dict[str, Any],
    ) -> PromptContextInputs:
        total_chapters = max(
            chapter_number,
            max((item.chapter_number for item in project.outlines), default=chapter_number),
        )
        platinum_writing_brief = (
            await self.prompt_service.get_prompt("platinum_writing_brief")
            or PLATINUM_WRITING_BRIEF_FALLBACK
        )

        genre_profile = None
        genre_prompt_injection = ""
        genre_pacing_config = None
        if getattr(settings, "enable_genre_adaptation", True):
            genre_name = blueprint_dict.get("genre") or ""
            if genre_name:
                from .genre_profile_service import GenreProfileService

                genre_profile = GenreProfileService.get_profile(genre_name)
                if genre_profile:
                    genre_prompt_injection = GenreProfileService.build_genre_prompt_injection(genre_profile)
                    genre_pacing_config = genre_profile.get("pacing_config")

        strand_info = None
        if config.pacing_model == "strand_weave":
            from .strand_weave_service import StrandWeaveService

            if genre_pacing_config:
                strand_kwargs = {
                    "quest_ratio": genre_pacing_config.get("quest_ratio", settings.strand_quest_ratio),
                    "fire_ratio": genre_pacing_config.get("fire_ratio", settings.strand_fire_ratio),
                    "constellation_ratio": genre_pacing_config.get("constellation_ratio", settings.strand_constellation_ratio),
                }
            else:
                strand_kwargs = {
                    "quest_ratio": settings.strand_quest_ratio,
                    "fire_ratio": settings.strand_fire_ratio,
                    "constellation_ratio": settings.strand_constellation_ratio,
                }
            strand_service = StrandWeaveService(
                total_chapters=total_chapters,
                interleave_interval=settings.strand_interleave_interval,
                **strand_kwargs,
            )
            strand_service.plan_strands()
            strand_info = strand_service.get_chapter_strand(chapter_number)

        platinum_rhythm_brief = build_platinum_rhythm_brief(
            chapter_number=chapter_number,
            total_chapters=total_chapters,
            outline_title=outline_title,
            outline_summary=outline_summary,
            chapter_mission=chapter_mission,
            genre_pacing_config=genre_pacing_config,
            strand_info=strand_info,
        )
        hook_continuity_brief = build_hook_continuity_brief(
            previous_summary=history_context["previous_summary"],
            previous_tail=history_context["previous_tail"],
            chapter_mission=chapter_mission,
        )
        emotion_expression_brief = self.prompt_assembly_service.build_emotion_expression_brief(
            history_context.get("completed_chapters", [])
        )

        return PromptContextInputs(
            total_chapters=total_chapters,
            platinum_writing_brief=platinum_writing_brief,
            genre_profile=genre_profile,
            genre_prompt_injection=genre_prompt_injection,
            genre_pacing_config=genre_pacing_config,
            strand_info=strand_info,
            platinum_rhythm_brief=platinum_rhythm_brief,
            hook_continuity_brief=hook_continuity_brief,
            emotion_expression_brief=emotion_expression_brief,
        )
