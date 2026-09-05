"""Render the expressive parts of a chapter mission without another LLM call.

These planning intentions must survive both mission-to-brief conversion and
scene context compression. Support the current nested and legacy flat formats.
"""
from __future__ import annotations

from typing import Any


def mission_value(mission: Any, *keys: str) -> Any:
    if not isinstance(mission, dict):
        return None
    for source in (mission.get("hard_constraints"), mission.get("soft_suggestions"), mission):
        if not isinstance(source, dict):
            continue
        for key in keys:
            value = source.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def inline_value(value: Any) -> str:
    if isinstance(value, dict):
        return "；".join(
            f"{key}：{inline_value(item)}"
            for key, item in value.items() if item not in (None, "", [], {})
        )
    if isinstance(value, (list, tuple)):
        return "；".join(inline_value(item) for item in value if item not in (None, "", [], {}))
    return str(value) if value is not None else ""


def build_emotional_continuity_brief(mission: Any) -> str:
    """Preserve chapter-wide intent; missing intent stays absent, never invented."""
    lines = []
    for label, keys in (
        ("章节功能", ("chapter_function", "chapter_type")),
        ("情绪走向与松弛点", ("emotion_curve",)),
        ("主动留白及原因", ("deliberate_omission",)),
        ("质感与笔墨分配", ("tone_guide",)),
        ("后续阅读期待", ("reader_promise",)),
    ):
        value = inline_value(mission_value(mission, *keys)).strip()
        if value:
            lines.append(f"- {label}：{value}")
    if not lines:
        return ""
    return "\n".join([
        "【情感与留白执行】",
        *lines,
        "- 按本章功能安排快慢与详略；松弛点在指定位置落实，不必每个场景重演整条情绪曲线。",
        "- 以上是写作意图，通过人物的选择、对白与后果呈现，不照抄情绪标签，不把主动留白解释给读者。",
    ])


def build_scene_expression_brief(scene: dict) -> str:
    """Scene-specific expressive details that the event skeleton cannot replace."""
    lines = []
    for key, label in (
        ("relationship_temp", "关系温度变化"),
        ("human_texture", "生活细节"),
        ("dialogue_noise", "对白中的打断、沉默或言外之意"),
        ("transition_out", "离场衔接"),
    ):
        value = inline_value(scene.get(key)).strip()
        if value:
            lines.append(f"- {label}：{value}")
    return "\n".join(lines)
