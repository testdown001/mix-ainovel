"""Bounded character motives and reading expectations shared by planning stages.

Only supplied material is used; a planned choice is not a canonical story fact.
"""
from __future__ import annotations

import json
from typing import Any


CHARACTER_FOCUS_FIELDS = {
    "character_name": "重点人物",
    "wants": "当下想得到或保住什么",
    "stakes": "得失为何对他重要",
    "choice": "本章行动或选择",
    "cost": "代价与后果",
    "relationship_change": "关系变化",
    "next_expectation": "后续阅读期待",
}
_PROTAGONIST_FIELDS = {
    "name": "姓名", "identity": "身份", "desire": "欲望", "flaw": "缺陷",
    "predicament": "困境", "charm_point": "读者站在他这边的依据",
}
_EMOTIONAL_FIELDS = {
    "cherished": "最舍不得", "exception": "会为谁破例", "key_relationship": "核心关系",
    "hard_choice": "两难选择", "emotional_promise": "情感承诺",
}
_CHARACTER_FIELDS = (
    "identity", "goals", "desire", "flaw", "personality", "predicament",
    "relationship_to_protagonist", "cherished", "fear", "values",
)


def _text(value: Any, limit: int = 300) -> str:
    if isinstance(value, str):
        return value.strip()[:limit]
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)[:limit]
    return ""


def clean_character_focus(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        key: text for key in CHARACTER_FOCUS_FIELDS
        if (text := _text(value.get(key), 100 if key == "character_name" else 400))
        and isinstance(value.get(key), str)
    }


def _bounded_group(title: str, lines: list[str], budget: int) -> str:
    """Keep whole semantic rows; never cut JSON or a character's name in half."""
    if not lines or budget <= len(title) + 1:
        return ""
    selected = [title]
    remaining = budget - len(title)
    for index, line in enumerate(lines):
        allocation = remaining // (len(lines) - index) - 1
        if len(line) > allocation and line.startswith("{") and allocation > 60:
            card = json.loads(line)
            while len(json.dumps(card, ensure_ascii=False)) > allocation and len(card) > 1:
                keys = [key for key in card if key != "name"]
                value_limit = max(8, (allocation - len(json.dumps({key: "" for key in card}))
                                      - len(card.get("name", ""))) // max(1, len(keys)))
                card = {key: value if key == "name" else value[:value_limit] for key, value in card.items()}
                if len(json.dumps(card, ensure_ascii=False)) > allocation:
                    card.pop(keys[-1])
            line = json.dumps(card, ensure_ascii=False)
        if len(line) > allocation and not line.startswith("{") and "：" in line:
            label, value = line.split("：", 1)
            value_limit = allocation - len(label) - 2
            if value_limit >= 8:
                line = label + "：" + value[:value_limit] + "…"
        if len(line) + 1 <= remaining and len(line) <= allocation:
            selected.append(line)
            remaining -= len(line) + 1
    return "\n".join(selected) if len(selected) > 1 else ""


def build_character_planning_context(
    blueprint: dict,
    dossier: dict | None = None,
    planning: dict | None = None,
    query: str = "",
    max_chars: int = 6000,
) -> str:
    """Build relevant, bounded source material without adding model calls.

    Each group gets a share of the budget so world/character descriptions cannot
    evict the relationship or emotional promise. Blank legacy projects stay blank.
    """
    blueprint = blueprint if isinstance(blueprint, dict) else {}
    dossier = dossier if isinstance(dossier, dict) else {}
    if isinstance(dossier.get("dossier"), dict):
        dossier = dossier["dossier"]
    planning = planning if isinstance(planning, dict) else {}
    focus = clean_character_focus(planning.get("character_focus"))
    protagonist = dossier.get("protagonist") or {}
    protagonist = protagonist if isinstance(protagonist, dict) else {}
    emotional = dossier.get("emotional_core") or {}
    emotional = emotional if isinstance(emotional, dict) else {}
    anticipation = dossier.get("anticipation") or {}
    anticipation = anticipation if isinstance(anticipation, dict) else {}
    raw_characters = blueprint.get("characters") or []
    raw_relationships = blueprint.get("relationships") or []
    characters = [c for c in raw_characters if isinstance(c, dict)] if isinstance(raw_characters, list) else []
    relationships = [r for r in raw_relationships if isinstance(r, dict)] if isinstance(raw_relationships, list) else []

    preferred = focus.get("character_name") or _text(protagonist.get("name"), 100)
    search = query + " " + json.dumps(focus, ensure_ascii=False)
    characters.sort(key=lambda c: (
        bool(_text(c.get("name"), 100) and _text(c.get("name"), 100) in search),
        bool(preferred and c.get("name") == preferred),
    ), reverse=True)
    names = {str(c.get("name")) for c in characters[:4] if c.get("name")}
    relationships.sort(key=lambda r: sum(
        bool(_text(r.get(k), 100) and (_text(r.get(k), 100) in search or r.get(k) in names))
        for k in ("from", "to", "character_from", "character_to")
    ), reverse=True)

    # Per-value limits adapt to the requested scene/chapter budget.
    limit = max(35, min(240, max_chars // 24))
    cards = []
    for character in characters[:6]:
        card = {"name": _text(character.get("name"), 100)}
        card.update({key: value for key in _CHARACTER_FIELDS
                     if (value := _text(character.get(key), limit))})
        if card["name"] and len(card) > 1:
            cards.append(json.dumps(card, ensure_ascii=False))
    relations = []
    for relationship in relationships[:6]:
        source = _text(relationship.get("character_from") or relationship.get("from"), 100)
        target = _text(relationship.get("character_to") or relationship.get("to"), 100)
        description = _text(relationship.get("description"), limit)
        if source and target and description:
            relations.append(f"{source} → {target}：{description}")

    groups = [
        ("[本章人物与阅读期待（规划意图，不是已发生事实）]",
         [f"{label}：{_text(focus[key], limit)}" for key, label in CHARACTER_FOCUS_FIELDS.items() if key in focus], 0.20),
        ("[主角行动依据]", [f"{label}：{value}" for key, label in _PROTAGONIST_FIELDS.items()
                            if (value := _text(protagonist.get(key), limit))], 0.12),
        ("[本书情感核心]", [f"{label}：{value}" for key, label in _EMOTIONAL_FIELDS.items()
                            if (value := _text(emotional.get(key), limit))], 0.20),
        ("[本章相关人物资料]", cards, 0.28),
        ("[核心关系与未解决的牵挂]", relations, 0.12),
        ("[已建立的读者承诺]", [f"{label}：{value}" for key, label in (
            ("ten_chapters", "前十章"), ("fifty_chapters", "阶段兑现"), ("long_term", "长线期待"))
            if (value := _text(anticipation.get(key), limit))], 0.08),
    ]
    active = [(title, lines, weight) for title, lines, weight in groups if lines]
    if not active or max_chars <= 0:
        return ""
    weight_total = sum(weight for _, _, weight in active)
    separator_budget = 2 * (len(active) - 1)
    available = max(0, max_chars - separator_budget)
    parts = [part for title, lines, weight in active
             if (part := _bounded_group(title, lines, int(available * weight / weight_total)))]
    return "\n\n".join(parts)
