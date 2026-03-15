from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional


class VersionGenerationService:
    """封装标准模式下的多版本生成与 AI 选优阶段。"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def run(
        self,
        *,
        prompt_input: str,
        writer_prompt: str,
        enhanced_context: Optional[Dict[str, Any]],
        version_count: int,
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
        config: Any,
        chapter_target_word_count: int,
        chapter_word_count_max: int,
        genre_profile: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        orchestrator = self.orchestrator
        version_style_hints = orchestrator.generation_policy_service.resolve_style_hints(
            enhanced_context, version_count
        )

        version_tasks = []
        for idx in range(version_count):
            style_hint = version_style_hints[idx] if idx < len(version_style_hints) else None
            version_tasks.append(
                orchestrator._generate_single_version(
                    index=idx,
                    prompt_input=prompt_input,
                    writer_prompt=writer_prompt,
                    style_hint=style_hint,
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
                )
            )

        versions = list(await asyncio.gather(*version_tasks))
        best_version_index, ai_review_result = await orchestrator._run_ai_review(
            versions=versions,
            chapter_mission=chapter_mission,
            user_id=user_id,
        )
        if versions:
            best_version_index = max(0, min(best_version_index, len(versions) - 1))
        else:
            best_version_index = 0

        return {
            "versions": versions,
            "best_version_index": best_version_index,
            "ai_review_result": ai_review_result,
        }
