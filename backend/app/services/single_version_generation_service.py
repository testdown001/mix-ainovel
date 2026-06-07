from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException

from ..core.config import settings
from ..utils.json_utils import (
    extract_text_from_json,
    is_probable_chapter_plain_text,
    remove_think_tags,
    sanitize_chapter_plain_text,
    unwrap_markdown_json,
)


class SingleVersionGenerationService:
    """封装单版本正文生成流程。"""

    def __init__(
        self,
        *,
        llm_service,
        guardrails,
        generation_policy_service,
        text_compression_service,
        preview_generation_service_factory: Callable[[], Any],
    ):
        self.llm_service = llm_service
        self.guardrails = guardrails
        self.generation_policy_service = generation_policy_service
        self.text_compression_service = text_compression_service
        self.preview_generation_service_factory = preview_generation_service_factory

    async def generate(
        self,
        *,
        index: int,
        prompt_input: str,
        writer_prompt: str,
        style_hint: Optional[Any],
        project_id: str,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        chapter_mission: Optional[dict],
        forbidden_characters: List[str],
        allowed_new_characters: List[str],
        user_id: int,
        writer_blueprint: Dict[str, Any],
        memory_context: Optional[str],
        enhanced_context: Optional[Dict[str, Any]],
        config: Any,
        target_word_count: int,
        max_word_count: int = 4000,
        genre_profile: Optional[Dict[str, Any]] = None,
        disable_guardrail_rewrite: bool = False,
        stream_callback: Optional[Callable[[str], Awaitable[None] | None]] = None,
    ) -> Dict[str, Any]:
        if isinstance(style_hint, dict):
            style_text = style_hint.get("text", "")
            temp_offset = float(style_hint.get("temp_offset", 0.0))
        elif isinstance(style_hint, str):
            style_text = style_hint
            temp_offset = 0.0
        else:
            style_text = ""
            temp_offset = 0.0

        base_temp = self.generation_policy_service.resolve_temperature(chapter_mission)
        resolved_temp = max(0.1, min(1.5, base_temp + temp_offset))
        metadata: Dict[str, Any] = {
            "chapter_mission": chapter_mission,
            "style_hint": style_hint,
            "pipeline": {"preset": config.preset},
            "resolved_temperature": resolved_temp,
        }

        content = ""
        used_direct_generation = False
        final_prompt_input = prompt_input
        dynamic_max_tokens = min(
            settings.writer_max_tokens,
            int(max_word_count * 1.5),
        )
        if getattr(config, "enable_preview", False):
            content, preview_meta = await self.generate_with_preview(
                project_id=project_id,
                chapter_number=chapter_number,
                outline_title=outline_title,
                outline_summary=outline_summary,
                writer_blueprint=writer_blueprint,
                memory_context=memory_context,
                style_hint=style_text or style_hint,
                enhanced_context=enhanced_context,
                target_word_count=target_word_count,
                user_id=user_id,
            )
            metadata["preview"] = preview_meta

        if not content:
            if style_text:
                final_prompt_input = f"[版本风格策略]\n{style_text}\n\n{final_prompt_input}"
            response = await self.llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=resolved_temp,
                user_id=user_id,
                timeout=180.0,
                response_format=None,
                max_tokens=dynamic_max_tokens,
                disable_thinking=not settings.writer_enable_thinking,
                on_chunk=stream_callback,
            )
            cleaned = remove_think_tags(response)
            content = unwrap_markdown_json(cleaned or response)
            used_direct_generation = True

        omniscient_tolerance = "medium"
        if genre_profile:
            from .genre_profile_service import GenreProfileService

            omniscient_tolerance = GenreProfileService.get_omniscient_tolerance(genre_profile)

        guardrail_result = self.guardrails.check(
            generated_text=content,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            pov=chapter_mission.get("pov") if chapter_mission else None,
            omniscient_tolerance=omniscient_tolerance,
        )
        guardrail_metadata = {"passed": guardrail_result.passed, "violations": []}

        if not guardrail_result.passed:
            guardrail_metadata["violations"] = [
                {"type": violation.type, "severity": violation.severity, "description": violation.description}
                for violation in guardrail_result.violations
            ]
            locally_patched = self.guardrails.apply_local_patches(content, guardrail_result)
            guardrail_metadata["local_patch_applied"] = locally_patched != content
            recheck_result = self.guardrails.check(
                generated_text=locally_patched,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                pov=chapter_mission.get("pov") if chapter_mission else None,
                omniscient_tolerance=omniscient_tolerance,
            )
            guardrail_metadata["post_patch_passed"] = recheck_result.passed

            if recheck_result.passed:
                content = locally_patched
            else:
                guardrail_metadata["post_patch_violations"] = [
                    {"type": violation.type, "severity": violation.severity, "description": violation.description}
                    for violation in recheck_result.violations
                ]
                content = locally_patched
                if not disable_guardrail_rewrite:
                    guardrail_metadata["deferred_llm_rewrite"] = True

        parsed_json = None
        extracted_text = None
        try:
            parsed_json = json.loads(content)
            extracted_text = extract_text_from_json(parsed_json)
        except Exception:
            parsed_json = None

        final_text = sanitize_chapter_plain_text(extracted_text or content)
        if not is_probable_chapter_plain_text(final_text) and used_direct_generation:
            retry_prompt_input = (
                f"{final_prompt_input}\n\n"
                "[上一次输出无效]\n"
                "你刚才输出了提示词、任务分析或编辑说明，而不是小说正文。\n"
                "现在必须直接写出本章小说正文：不要分析、不要解释、不要标题、不要 JSON、不要列提纲。"
            )
            retry_response = await self.llm_service.get_llm_response(
                system_prompt=(
                    f"{writer_prompt}\n\n"
                    "硬性输出要求：只输出小说章节正文。第一个字必须是正文，不允许输出分析任务、原文本分析、"
                    "角色目标限制、编辑说明、标题、JSON 或 Markdown。"
                ),
                conversation_history=[{"role": "user", "content": retry_prompt_input}],
                temperature=max(0.2, resolved_temp - 0.15),
                user_id=user_id,
                timeout=180.0,
                response_format=None,
                max_tokens=dynamic_max_tokens,
                disable_thinking=not settings.writer_enable_thinking,
                on_chunk=stream_callback,
            )
            retry_cleaned = remove_think_tags(retry_response)
            content = unwrap_markdown_json(retry_cleaned or retry_response)
            parsed_json = None
            extracted_text = None
            try:
                parsed_json = json.loads(content)
                extracted_text = extract_text_from_json(parsed_json)
            except Exception:
                parsed_json = None
            final_text = sanitize_chapter_plain_text(extracted_text or content)
            metadata["invalid_output_retry"] = True

        if not is_probable_chapter_plain_text(final_text):
            raise HTTPException(status_code=502, detail="章节生成失败：模型没有返回小说正文，请重试")

        overflow_threshold = int(max_word_count * 1.02)
        if len(final_text) > overflow_threshold:
            compressed = await self.text_compression_service.compress_overlength(
                final_text,
                target_max=max_word_count,
                user_id=user_id,
            )
            metadata["word_count_compression"] = {
                "original_length": len(final_text),
                "compressed_length": len(compressed),
                "target_max": max_word_count,
            }
            final_text = compressed

        metadata["guardrail"] = guardrail_metadata
        if parsed_json is not None:
            metadata["parsed_json"] = parsed_json

        return {
            "index": index,
            "content": final_text,
            "metadata": metadata,
        }

    async def generate_with_preview(
        self,
        *,
        project_id: str,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        writer_blueprint: Dict[str, Any],
        memory_context: Optional[str],
        style_hint: Optional[str],
        enhanced_context: Optional[Dict[str, Any]],
        target_word_count: int,
        user_id: int,
    ):
        preview_service = self.preview_generation_service_factory()
        blueprint_context = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)
        extra_constraints = []
        if enhanced_context:
            if enhanced_context.get("constitution"):
                extra_constraints.append(enhanced_context["constitution"])
            if enhanced_context.get("writer_persona"):
                extra_constraints.append(enhanced_context["writer_persona"])

        if extra_constraints:
            blueprint_context = blueprint_context + "\n\n" + "\n\n".join(extra_constraints)

        preview_result = await preview_service.generate_with_preview(
            project_id=project_id,
            chapter_number=chapter_number,
            outline={"title": outline_title, "summary": outline_summary},
            blueprint_context=blueprint_context,
            emotion_context="（无情绪曲线指导）",
            memory_context=memory_context or "（无记忆层上下文）",
            target_word_count=target_word_count,
            style_hint=style_hint or "",
            user_id=user_id,
        )
        return preview_result.get("full_chapter", ""), preview_result
