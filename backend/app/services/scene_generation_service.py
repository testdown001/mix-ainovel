from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..core.config import settings
from ..utils.json_utils import remove_think_tags, sanitize_chapter_plain_text, unwrap_markdown_json
from .llm_service import LLMResponseTruncated

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
        model_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 按所选模型(章鱼1.0/2.0/3.0)解析真实通道；缺省 None → 默认 llm.*
        model_override = None
        if model_code:
            model_override = await self.llm_service._resolve_config_by_model_code(model_code)
        metadata: Dict[str, Any] = {
            "chapter_mission": chapter_mission,
            "pipeline": {"preset": "literary", "mode": "scene_by_scene"},
            "resolved_temperature": self.generation_policy_service.resolve_temperature(chapter_mission),
        }

        scenes = (chapter_mission or {}).get("scene_list") or []
        if not scenes:
            scenes = self._load_scene_plan(prompt_sections_data.get("scene_plan"))
        if not scenes or len(scenes) < 2:
            scenes = self.build_fallback_scenes(chapter_mission)

        # 硬约束（禁止人物/POV/章节目标）单独成段、不参与压缩，每个场景完整携带；
        # compress_context 只压叙事性上下文（骨架/前情等）——修复场景2+头部截断丢约束。
        hard_constraints = self.build_hard_constraints(prompt_sections_data, chapter_mission)
        core_context = self.build_slim_context(prompt_sections_data)
        chapter_parts: List[str] = []
        scene_timings: List[int] = []
        missing_scenes: List[int] = []

        for index, scene in enumerate(scenes):
            scene_start = time.perf_counter()
            is_first = index == 0
            is_last = index == len(scenes) - 1
            scene_prompt_parts = []

            if hard_constraints:
                scene_prompt_parts.append(hard_constraints)
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
            dependencies = scene.get("dependencies") or []
            required_evidence = scene.get("required_evidence") or []
            characters = scene.get("characters") or []
            verification_hints = scene.get("verification_hints") or []

            scene_instruction = f"[本场景任务——场景 {index + 1}/{len(scenes)}]\n"
            scene_instruction += f"- 目标：{scene_goal}\n"
            if dependencies:
                scene_instruction += f"- 依赖场景：{'、'.join(str(item) for item in dependencies)}\n"
            if required_evidence:
                scene_instruction += f"- 必须参考证据源：{'、'.join(str(item) for item in required_evidence)}\n"
            if characters:
                scene_instruction += f"- 重点人物：{'、'.join(str(item) for item in characters)}\n"
            if scene_location:
                scene_instruction += f"- 地点：{scene_location}\n"
            if scene_conflict:
                scene_instruction += f"- 阻力/冲突：{scene_conflict}\n"
            scene_instruction += f"- 目标字数：约{scene_words}字\n"
            if verification_hints:
                scene_instruction += f"- 完成后必须满足：{'、'.join(str(item) for item in verification_hints)}\n"
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

            scene_call_kwargs: Dict[str, Any] = dict(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": scene_prompt}],
                temperature=resolved_temp,
                user_id=user_id,
                timeout=60.0,
                response_format=None,
                disable_thinking=not settings.writer_enable_thinking,
                config_override=model_override,
                fail_on_truncation=True,
            )
            scene_max_tokens = min(4096, int(max(700, scene_words) * 1.8))
            # 场景级通用容错：任何异常（超时/5xx 等）重试一次，仍失败则以空场景继续拼章，
            # 不炸整章（与截断的场景级降级一致）；截断降级在 _invoke_scene_llm 内处理。
            response: Optional[str] = None
            try:
                response = await self._invoke_scene_llm(
                    scene_max_tokens=scene_max_tokens,
                    scene_call_kwargs=scene_call_kwargs,
                    scene_no=index + 1,
                    total=len(scenes),
                )
            except Exception as exc:
                logger.warning("场景 %d/%d 生成失败（%s），重试一次", index + 1, len(scenes), exc)
                try:
                    response = await self._invoke_scene_llm(
                        scene_max_tokens=scene_max_tokens,
                        scene_call_kwargs=scene_call_kwargs,
                        scene_no=index + 1,
                        total=len(scenes),
                    )
                except Exception as retry_exc:
                    logger.warning(
                        "场景 %d/%d 重试后仍失败（%s），以空场景继续拼章",
                        index + 1, len(scenes), retry_exc,
                    )
            scene_text = ""
            if response:
                cleaned = remove_think_tags(response)
                scene_text = sanitize_chapter_plain_text(unwrap_markdown_json(cleaned or response))
            if scene_text:
                chapter_parts.append(scene_text)
            else:
                logger.warning("场景 %d/%d 无有效输出，记为缺失场景继续拼章", index + 1, len(scenes))
                missing_scenes.append(index + 1)
            scene_timings.append(int((time.perf_counter() - scene_start) * 1000))

        if not chapter_parts:
            raise RuntimeError(f"文学模式全部 {len(scenes)} 个场景生成失败，无法拼章")

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
        if missing_scenes:
            metadata["missing_scenes"] = missing_scenes
        metadata["scene_plan_applied"] = bool(prompt_sections_data.get("scene_plan"))
        return {"index": 0, "content": content, "metadata": metadata}

    async def _invoke_scene_llm(
        self,
        *,
        scene_max_tokens: int,
        scene_call_kwargs: Dict[str, Any],
        scene_no: int,
        total: int,
    ) -> str:
        """单场景 LLM 调用，内置截断降级：提升 token 上限重试一次，仍截断保留半截文本。"""
        try:
            return await self.llm_service.get_llm_response(
                max_tokens=scene_max_tokens,
                **scene_call_kwargs,
            )
        except LLMResponseTruncated as first_truncation:
            raised_max_tokens = min(settings.writer_max_tokens, int(scene_max_tokens * 1.5))
            if raised_max_tokens <= scene_max_tokens:
                # writer_max_tokens 配置低于首次上限时「提升」会反降：同额/降额重试无意义，直接保留首次部分文本
                logger.warning(
                    "场景 %d/%d 被截断且 max_tokens 已达配置顶格 (%d)，保留部分内容 (%d 字符)",
                    scene_no, total, scene_max_tokens, len(first_truncation.partial_text),
                )
                return first_truncation.partial_text
            try:
                return await self.llm_service.get_llm_response(
                    max_tokens=raised_max_tokens,
                    **scene_call_kwargs,
                )
            except LLMResponseTruncated as exc:
                logger.warning(
                    "场景 %d/%d 提升 max_tokens=%d 重试后仍被截断，保留部分内容 (%d 字符)",
                    scene_no, total, raised_max_tokens, len(exc.partial_text),
                )
                return exc.partial_text

    @staticmethod
    def _load_scene_plan(raw: Any) -> List[dict]:
        if not raw:
            return []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return []
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        return []

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
    def build_hard_constraints(
        prompt_sections_data: Dict[str, Any],
        chapter_mission: Optional[dict],
    ) -> str:
        """硬约束段（章节目标/POV/禁止人物）：不参与压缩，每个场景完整携带。"""
        parts: List[str] = []
        chapter_goals = prompt_sections_data.get("chapter_goals", "")
        if chapter_goals:
            parts.append(str(chapter_goals))
        pov = (chapter_mission or {}).get("pov")
        if pov:
            parts.append(f"[视角硬约束]\n本章视角(POV)：{pov}，全章不得漂移。")
        forbidden = prompt_sections_data.get("forbidden_characters", "")
        if forbidden:
            parts.append(f"[禁止出场人物——硬约束]\n以下角色严禁在本章出现：{forbidden}")
        if not parts:
            return ""
        return "[硬约束——每个场景都必须遵守]\n\n" + "\n\n".join(parts)

    @staticmethod
    def build_slim_context(prompt_sections_data: Dict[str, Any]) -> str:
        # 叙事性上下文（可压缩）；chapter_goals/forbidden_characters 已移入 build_hard_constraints
        priority_keys = [
            "mission_brief", "director_script",
            "story_skeleton", "previous_summary", "previous_tail",
            "skill_instructions",
            "scene_plan", "context_strategy",
            "writer_blueprint",
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
