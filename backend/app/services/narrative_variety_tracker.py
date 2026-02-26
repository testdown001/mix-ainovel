# AIMETA P=叙事多样性追踪_跨章结构去重|R=模式检测_差异化约束|NR=不含API路由|E=NarrativeVarietyTracker|X=internal|A=追踪|D=none|S=compute|RD=./README.ai
"""
NarrativeVarietyTracker: 跨章节叙事多样性追踪

分析最近 N 章的叙事模式（开头类型、结尾类型、结构类型、情绪基调、高潮位置），
当检测到连续重复时，输出强制差异化约束注入导演脚本生成。

纯 Python 计算，零 LLM 成本。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


CHAPTER_STRUCTURE_TEMPLATES = [
    {
        "type": "cold_open",
        "label": "冷开场",
        "description": "开头直接是动作/对话/画面的中段，无铺垫，读者被扔进正在发生的事件里",
        "suitable_for": ["action", "climax", "turning"],
    },
    {
        "type": "single_scene",
        "label": "单场景长镜头",
        "description": "整章一个不间断场景，保持实时感，像电影长镜头",
        "suitable_for": ["dialogue_heavy", "climax", "revelation"],
    },
    {
        "type": "montage",
        "label": "蒙太奇",
        "description": "多个短片段快速切换，时间压缩，用对比和并列推进",
        "suitable_for": ["training", "preparation", "daily"],
    },
    {
        "type": "flashback_intercut",
        "label": "倒叙揭开",
        "description": "先写结果/现状，再回溯过程，制造认知反转",
        "suitable_for": ["revelation", "turning", "mystery"],
    },
    {
        "type": "dialogue_dominant",
        "label": "对话主体",
        "description": "90% 对话，极少叙述，靠角色声音推进一切",
        "suitable_for": ["negotiation", "intelligence", "relationship"],
    },
    {
        "type": "standard_three_act",
        "label": "标准三段",
        "description": "经典铺垫→发展→高潮，稳妥可靠",
        "suitable_for": ["default"],
    },
]


@dataclass
class ChapterPattern:
    chapter_number: int = 0
    opening_type: str = ""
    ending_type: str = ""
    structure_type: str = "standard_three_act"
    dominant_emotion: str = ""
    dialogue_ratio: float = 0.0
    peak_position: float = 0.6

    @classmethod
    def from_mission_and_text(
        cls,
        chapter_number: int,
        chapter_mission: Optional[dict],
        chapter_text: Optional[str],
    ) -> "ChapterPattern":
        pattern = cls(chapter_number=chapter_number)

        if chapter_mission:
            pattern.opening_type = chapter_mission.get("opening_hook_type", "")
            ending_design = chapter_mission.get("anti_ai_controls", {}).get("ending_design", {})
            pattern.ending_type = chapter_mission.get("chapter_end_style", "")
            emotion = chapter_mission.get("emotion_curve", {})
            if isinstance(emotion, dict):
                pattern.dominant_emotion = emotion.get("type", "")

            sat = chapter_mission.get("satisfaction_design", {})
            if isinstance(sat, dict):
                pattern.dominant_emotion = pattern.dominant_emotion or sat.get("type", "")

        if chapter_text:
            total_len = len(chapter_text)
            dialogue_chars = sum(
                len(m.group())
                for m in re.finditer(r'[\u201c\u300c].+?[\u201d\u300d]', chapter_text)
            )
            pattern.dialogue_ratio = dialogue_chars / max(1, total_len)

        return pattern


class NarrativeVarietyTracker:
    """追踪最近 N 章的叙事模式，生成差异化约束。"""

    @staticmethod
    def analyze_variety(
        recent_patterns: List[ChapterPattern],
        current_chapter_number: int,
    ) -> Dict[str, str]:
        if len(recent_patterns) < 2:
            return {}

        constraints: Dict[str, str] = {}
        last = recent_patterns[-1]
        second_last = recent_patterns[-2] if len(recent_patterns) >= 2 else None

        if second_last and last.opening_type and last.opening_type == second_last.opening_type:
            constraints["opening_variety"] = (
                f"前两章都使用了「{last.opening_type}」开场，本章必须换用其他开场方式。"
                f"建议从以下选择：冷开场（直接进入动作中段）、对话开场、感官开场、倒叙开场"
            )

        if len(recent_patterns) >= 2:
            recent_endings = [p.ending_type for p in recent_patterns[-2:] if p.ending_type]
            if len(recent_endings) >= 2 and len(set(recent_endings)) == 1:
                constraints["ending_variety"] = (
                    f"前两章都使用了「{recent_endings[0]}」结尾，本章必须换用其他收束方式。"
                    f"可选：热血型收束、爽感型收束、悬念型收束、硬切收束"
                )

        if len(recent_patterns) >= 3:
            recent_emotions = [p.dominant_emotion for p in recent_patterns[-3:] if p.dominant_emotion]
            if len(recent_emotions) >= 3 and len(set(recent_emotions)) == 1:
                constraints["emotion_variety"] = (
                    f"前三章主导情绪都是「{recent_emotions[0]}」，读者会审美疲劳。"
                    f"本章必须切换情绪基调——即使主线剧情氛围不变，也要在子情绪上做变化"
                )

        if len(recent_patterns) >= 3:
            recent_ratios = [p.dialogue_ratio for p in recent_patterns[-3:]]
            avg_ratio = sum(recent_ratios) / len(recent_ratios)
            if all(abs(r - avg_ratio) < 0.08 for r in recent_ratios):
                if avg_ratio > 0.45:
                    constraints["dialogue_variety"] = "前几章对话占比都偏高，本章适当增加叙述/描写比重"
                elif avg_ratio < 0.25:
                    constraints["dialogue_variety"] = "前几章对话占比偏低，本章需要更多对话驱动"

        return constraints

    @staticmethod
    def suggest_structure(
        recent_patterns: List[ChapterPattern],
        chapter_mission: Optional[dict] = None,
    ) -> Dict[str, str]:
        recent_types = [p.structure_type for p in recent_patterns[-3:] if p.structure_type]

        suitable = []
        if chapter_mission:
            chapter_type = chapter_mission.get("chapter_type", "")
            macro_beat = chapter_mission.get("macro_beat", "")
            for tmpl in CHAPTER_STRUCTURE_TEMPLATES:
                if tmpl["type"] in recent_types:
                    continue
                suitable.append(tmpl)
        else:
            suitable = [t for t in CHAPTER_STRUCTURE_TEMPLATES if t["type"] not in recent_types]

        if not suitable:
            suitable = CHAPTER_STRUCTURE_TEMPLATES

        chosen = suitable[0]
        return {
            "suggested_structure": chosen["type"],
            "structure_label": chosen["label"],
            "structure_description": chosen["description"],
        }

    @staticmethod
    def format_constraints_for_prompt(constraints: Dict[str, str]) -> str:
        if not constraints:
            return ""
        lines = ["[跨章叙事差异化约束——避免结构重复]"]
        for key, value in constraints.items():
            if key.startswith("suggested_"):
                continue
            lines.append(f"- {value}")
        return "\n".join(lines)
