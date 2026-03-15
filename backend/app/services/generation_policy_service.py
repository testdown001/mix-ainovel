from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.constants import CHAPTER_MAX_WORDS, CHAPTER_MIN_WORDS


class GenerationPolicyService:
    """承载章节生成中的纯策略判断逻辑。"""

    @staticmethod
    def resolve_word_count_bounds() -> Tuple[int, int, int]:
        try:
            min_words = int(getattr(settings, "writer_chapter_word_count_min", CHAPTER_MIN_WORDS))
        except (TypeError, ValueError):
            min_words = CHAPTER_MIN_WORDS
        try:
            max_words = int(getattr(settings, "writer_chapter_word_count_max", CHAPTER_MAX_WORDS))
        except (TypeError, ValueError):
            max_words = CHAPTER_MAX_WORDS

        if min_words < 1:
            min_words = CHAPTER_MIN_WORDS
        if max_words < min_words:
            max_words = min_words

        target_words = min_words + (max_words - min_words) // 2
        return min_words, max_words, target_words

    @staticmethod
    def resolve_style_hints(
        enhanced_context: Optional[Dict[str, Any]],
        version_count: int,
    ) -> List[str]:
        if enhanced_context and enhanced_context.get("version_style_hints"):
            hints = enhanced_context["version_style_hints"]
            if isinstance(hints, list) and hints:
                return hints[:version_count]
        return [
            "情绪更细腻，节奏更慢，多写内心戏和感官描写",
            "冲突更强，节奏更快，多写动作和对话",
            "悬念更重，多埋伏笔，结尾钩子更强",
        ][:version_count]

    @staticmethod
    def resolve_pov_character(chapter_mission: Optional[dict]) -> Optional[str]:
        if not chapter_mission:
            return None
        return chapter_mission.get("pov") or chapter_mission.get("pov_character")

    @staticmethod
    def resolve_temperature(chapter_mission: Optional[dict]) -> float:
        if not chapter_mission:
            return 0.75

        macro_beat = (chapter_mission.get("macro_beat") or "").lower()
        sat_type = (chapter_mission.get("satisfaction_design") or {}).get("type", "")

        if sat_type and sat_type != "无（蓄力中）":
            return 0.85
        for keyword in ("高潮", "爆发", "反转", "逆袭", "决战", "爽"):
            if keyword in macro_beat:
                return 0.85
        for keyword in ("虐", "刀", "离别", "牺牲", "背叛", "死亡", "失去"):
            if keyword in macro_beat:
                return 0.75
        for keyword in ("蓄力", "铺垫", "布局", "积蓄", "准备", "酝酿"):
            if keyword in macro_beat:
                return 0.65
        for keyword in ("过渡", "衔接", "日常", "休整", "喘息"):
            if keyword in macro_beat:
                return 0.60
        return 0.75

    @staticmethod
    def resolve_literary_intensity_signal(chapter_mission: Optional[dict]) -> str:
        if not chapter_mission:
            return ""
        chapter_type = str(chapter_mission.get("chapter_type", "")).lower()
        macro_beat = str(chapter_mission.get("macro_beat_description", "")).lower()
        sat_type = str((chapter_mission.get("satisfaction_design") or {}).get("type", "")).lower()
        return f"{chapter_type} {macro_beat} {sat_type}".strip()

    def resolve_literary_postprocess_profile(
        self,
        *,
        config: Any,
        chapter_mission: Optional[dict],
        target_word_count: int,
    ) -> Dict[str, Any]:
        profile = {
            "adaptive_enabled": bool(config.literary_adaptive_postprocess),
            "enable_prose_sculpting": bool(config.enable_prose_sculpting),
            "enable_golden_paragraph": bool(config.enable_golden_paragraph),
            "enable_humanization": bool(config.enable_humanization),
            "reason": "config_static",
        }
        if not config.literary_adaptive_postprocess:
            return profile

        signal = self.resolve_literary_intensity_signal(chapter_mission)
        short_target_threshold = int(getattr(settings, "writer_literary_adaptive_short_target", 2800))
        is_short_target = target_word_count <= short_target_threshold
        is_high_intensity = any(
            keyword in signal for keyword in ("高潮", "爆发", "决战", "反转", "逆袭", "巅峰", "climax", "boss", "twist")
        )
        is_low_intensity = any(
            keyword in signal for keyword in ("过渡", "衔接", "铺垫", "日常", "休整", "喘息", "setup", "transition", "slice")
        )

        if is_low_intensity:
            profile["enable_golden_paragraph"] = False
            profile["reason"] = "low_intensity"
        if is_low_intensity and is_short_target:
            profile["enable_prose_sculpting"] = False
            profile["reason"] = "low_intensity_short_target"
        if is_short_target and not is_high_intensity:
            profile["enable_humanization"] = False
            if profile["reason"] == "config_static":
                profile["reason"] = "short_target"

        profile["intensity_signal"] = signal[:120]
        profile["target_word_count"] = target_word_count
        profile["short_target_threshold"] = short_target_threshold
        return profile

    @staticmethod
    def build_stage_flags(config: Any) -> Dict[str, bool]:
        return {
            "preview": config.enable_preview,
            "optimizer": config.enable_optimizer,
            "polish": config.enable_polish,
            "mission_brief": config.enable_mission_brief,
            "consistency": config.enable_consistency,
            "enrichment": config.enable_enrichment,
            "constitution": config.enable_constitution,
            "persona": config.enable_persona,
            "six_dimension": config.enable_six_dimension,
            "reader_sim": config.enable_reader_sim,
            "self_critique": config.enable_self_critique,
            "memory": config.enable_memory,
            "rag": config.enable_rag,
            "rag_mode": config.rag_mode == "two_stage",
            "scene_by_scene": config.enable_scene_by_scene,
            "prose_sculpting": config.enable_prose_sculpting,
            "golden_paragraph": config.enable_golden_paragraph,
            "reference_prose": config.enable_reference_prose,
            "voice_samples": config.enable_voice_samples,
            "narrative_variety": config.enable_narrative_variety,
            "slim_prompt": config.use_slim_prompt,
            "literary_adaptive_postprocess": config.literary_adaptive_postprocess,
            "fast_path": config.enable_fast_path,
            "disable_guardrail_rewrite": config.disable_guardrail_rewrite,
            "local_anti_hallucination": config.use_local_anti_hallucination,
            "power_system": config.enable_power_system,
            "character_relationships": config.enable_character_relationships,
            "trajectory_analysis": config.enable_trajectory_analysis,
        }
