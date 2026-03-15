from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..core.config import settings
from ..utils.json_utils import remove_think_tags, sanitize_chapter_plain_text, unwrap_markdown_json

logger = logging.getLogger(__name__)


class SceneGenerationService:
    """封装文学模式下的 scene-by-scene 生成流程。"""

    def __init__(self, llm_service, guardrails, generation_policy_service, text_compression_service):
        self.llm_service = llm_service
        self.guardrails = guardrails
        self.generation_policy_service = generation_policy_service
        self.text_compression_service = text_compression_service

    async def generate_scene_by_scene(
        self,
        *,
        prompt_sections_data: Dict[str, Any],
        writer_prompt: str,
        chapter_mission: Optional[dict],
        forbidden_characters: List[str],
        allowed_new_characters: List[str],
        user_id: int,
        genre_profile: Optional[Dict[str, Any]] = None,
        voice_samples_text: str = "",
        max_word_count: int = 0,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "chapter_mission": chapter_mission,
            "pipeline": {"preset": "literary", "mode": "scene_by_scene"},
            "resolved_temperature": self.generation_policy_service.resolve_temperature(chapter_mission),
        }

        scenes = (chapter_mission or {}).get("scene_list") or []
        if not scenes or len(scenes) < 2:
            scenes = self.build_fallback_scenes(chapter_mission)

        core_context = self.build_slim_context(prompt_sections_data)
        chapter_parts: List[str] = []
        scene_timings: List[int] = []

        for index, scene in enumerate(scenes):
            scene_start = time.perf_counter()
            is_first = index == 0
            is_last = index == len(scenes) - 1
            scene_prompt_parts = []

            if is_first:
                scene_prompt_parts.append(core_context)
            else:
                scene_prompt_parts.append("[精简上下文]\n" + self.compress_context(core_context, max_len=1500))

            if chapter_parts:
                recent_text = "\n\n".join(chapter_parts)
                if len(recent_text) > 2000:
                    recent_text = "（前文省略）\n\n" + recent_text[-2000:]
                scene_prompt_parts.append(f"[已写正文——你要无缝接续]\n{recent_text}")

            scene_goal = scene.get("goal", "推进剧情")
            scene_words = scene.get("target_words", 700)
            scene_location = scene.get("location", "")
            scene_conflict = scene.get("conflict", "")
            human_texture = scene.get("human_texture", [])
            dialogue_noise = scene.get("dialogue_noise", "")

            scene_instruction = f"[本场景任务——场景 {index + 1}/{len(scenes)}]\n"
            scene_instruction += f"- 目标：{scene_goal}\n"
            if scene_location:
                scene_instruction += f"- 地点：{scene_location}\n"
            if scene_conflict:
                scene_instruction += f"- 阻力/冲突：{scene_conflict}\n"
            scene_instruction += f"- 目标字数：约{scene_words}字\n"
            if human_texture:
                scene_instruction += f"- 生活噪音：{'、'.join(human_texture)}\n"
            if dialogue_noise:
                scene_instruction += f"- 对话噪音：{dialogue_noise}\n"
            if is_first:
                scene_instruction += "- 这是开篇，需要吸引读者\n"
            if is_last:
                scene_instruction += "- 这是本章最后一个场景，结尾必须落在具体动作/画面上，戛然而止\n"
            scene_prompt_parts.append(scene_instruction)

            if voice_samples_text and is_first:
                scene_prompt_parts.append(voice_samples_text)

            scene_prompt = "\n\n".join(scene_prompt_parts)
            resolved_temp = self.generation_policy_service.resolve_temperature(chapter_mission)
            if is_last:
                resolved_temp = min(resolved_temp + 0.05, 0.95)

            response = await self.llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": scene_prompt}],
                temperature=resolved_temp,
                user_id=user_id,
                timeout=60.0,
                response_format=None,
                max_tokens=min(4096, int(max(700, scene_words) * 1.8)),
                disable_thinking=not settings.writer_enable_thinking,
            )
            cleaned = remove_think_tags(response)
            scene_text = sanitize_chapter_plain_text(unwrap_markdown_json(cleaned or response))
            if scene_text:
                chapter_parts.append(scene_text)
            scene_timings.append(int((time.perf_counter() - scene_start) * 1000))

        content = "\n\n".join(chapter_parts)
        if max_word_count and len(content) > max_word_count:
            logger.warning("场景拼接总字数超限 (%d > %d)，截断", len(content), max_word_count)
            content = self.text_compression_service.hard_trim_to_limit(content, max_word_count)

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
        if not guardrail_result.passed:
            content = self.guardrails.apply_local_patches(content, guardrail_result)

        metadata["scene_timings_ms"] = scene_timings
        metadata["scene_count"] = len(scenes)
        return {"index": 0, "content": content, "metadata": metadata}

    @staticmethod
    def build_fallback_scenes(chapter_mission: Optional[dict]) -> List[dict]:
        word_budget = (chapter_mission or {}).get("word_budget", {})
        raw_total = word_budget.get("total", 3500) if isinstance(word_budget, dict) else 3500
        total = raw_total if isinstance(raw_total, (int, float)) and raw_total > 0 else 3500
        return [
            {"goal": "开篇：承接上文，建立本章情境", "target_words": int(total * 0.25), "scene": "1"},
            {"goal": "发展：推进核心冲突", "target_words": int(total * 0.45), "scene": "2"},
            {"goal": "高潮+收束：情绪峰值，刀切结尾", "target_words": int(total * 0.30), "scene": "3"},
        ]

    @staticmethod
    def build_slim_context(prompt_sections_data: Dict[str, Any]) -> str:
        priority_keys = [
            "chapter_goals", "mission_brief", "director_script",
            "story_skeleton", "previous_summary", "previous_tail",
            "skill_instructions",
            "writer_blueprint", "forbidden_characters",
            "reference_prose", "fusion_dna",
        ]
        parts = []
        for key in priority_keys:
            value = prompt_sections_data.get(key, "")
            if value:
                parts.append(str(value)[:2000])
        return "\n\n".join(parts)

    @staticmethod
    def compress_context(context: str, max_len: int = 1500) -> str:
        if len(context) <= max_len:
            return context
        return context[:max_len] + "\n（上下文已压缩）"
