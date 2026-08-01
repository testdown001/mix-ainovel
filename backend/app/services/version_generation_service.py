from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VersionGenerationService:
    """封装标准模式下的多版本生成与 AI 选优阶段。"""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def run(
        self,
        *,
        prompt_input: str,
        prompt_sections: Optional[list] = None,
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

        # ---- 两遍制第一遍：只给事实与方向，把规则留到第二遍 ----
        # 动机见 two_pass_draft_service：26 个段落一次性堆进单次生成，其中约一半是
        # 「不许犯什么错」，模型的注意力被清单吃掉，写出来没毛病也没劲。
        two_pass = bool(getattr(config, "enable_two_pass_draft", False)) and bool(prompt_sections)
        draft_input = prompt_input
        if two_pass:
            from .two_pass_draft_service import TwoPassDraftService

            draft_sections, constraint_sections = TwoPassDraftService.partition_sections(prompt_sections)
            if constraint_sections and draft_sections:
                draft_input = TwoPassDraftService.build_draft_input(draft_sections)
                logger.info(
                    "两遍制第一遍：草稿段 %d / 规则段 %d（规则留到改写遍）",
                    len(draft_sections), len(constraint_sections),
                )
            else:
                # 切不出两侧就退回单遍，别为了用特性而用特性
                two_pass = False

        version_tasks = []
        for idx in range(version_count):
            style_hint = version_style_hints[idx] if idx < len(version_style_hints) else None
            version_tasks.append(
                orchestrator.single_version_generation_service.generate(
                    index=idx,
                    prompt_input=draft_input,
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

        # ---- 两遍制第二遍：只对选中的最佳稿施加规则做改写（不是 N 稿都改，省调用）----
        two_pass_report = None
        if two_pass and versions:
            from .two_pass_draft_service import TwoPassDraftService
            from ..utils.json_utils import is_probable_chapter_plain_text

            best = versions[best_version_index]
            revised, two_pass_report = await TwoPassDraftService().rewrite(
                draft_text=best.get("content") or "",
                sections=prompt_sections or [],
                llm_service=orchestrator.llm_service,
                prompt_service=orchestrator.prompt_service,
                user_id=user_id,
                target_word_count=chapter_target_word_count,
                validator=is_probable_chapter_plain_text,
            )
            if two_pass_report.get("applied"):
                best["content"] = revised
                metadata = best.get("metadata")
                if isinstance(metadata, dict):
                    metadata["two_pass"] = two_pass_report

        return {
            "versions": versions,
            "two_pass": two_pass_report,
            "best_version_index": best_version_index,
            "ai_review_result": ai_review_result,
        }
