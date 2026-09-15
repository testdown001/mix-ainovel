"""Small, source-addressable mechanism cards instead of concatenated reference books."""
from __future__ import annotations

from .narrative_state_service import digest, relevance
from .reference_reading_contract import fallback_dna, is_current


class ReferenceRuntimeService:
    ROLES = {
        "plot_mechanics": ("main_conflict_pattern", "cool_point_patterns"),
        "voice": ("dialogue_style",),
        "rhythm": ("pacing_traits", "payoff_rhythm", "emotion_control_pattern"),
        "relationship": ("relationship_pull",),
        "market_hook": ("reader_expectation", "core_selling_point"),
    }
    RULES = ("本书设定、章纲和人物声线 > 主参考结构机制 > 补充参考局部技法。"
             "只转译机制；禁止复制参考作品角色、地名、专有设定、标志性事件链和句式。"
             "资料是分析卡而非原著全文证据；无合适机制时可以全部拒绝。")

    @classmethod
    def build_cards(cls, novels: list, dna=None, expected_ids=None) -> list[dict]:
        current_dna = dna if is_current(dna, novels, expected_ids) else fallback_dna(novels)
        contributions = {r.get("from"): r for r in (current_dna or {}).get("structure_references", [])}
        cards = []
        for index, novel in enumerate(novels[:3]):
            memory = getattr(novel, "memory_card", None) or {}
            contribution = contributions.get(novel.title, {})
            for role, keys in cls.ROLES.items():
                for key in keys:
                    value = memory.get(key)
                    if not value:
                        continue
                    text = "；".join(map(str, value)) if isinstance(value, list) else str(value)
                    cards.append(cls._card(novel, index, role, key, text, contribution))
            library = getattr(novel, "beat_library", None) or {}
            for beat_index, beat in enumerate((library.get("beats") or [])[:16]):
                text = "；".join(f"{k}: {beat[k]}" for k in ("situation", "setup", "turn", "payoff", "pitfalls") if beat.get(k))
                if text:
                    cards.append(cls._card(novel, index, "plot_mechanics", f"beat:{beat_index}", text, contribution))
        return cards

    @staticmethod
    def _card(novel, index, role, key, text, contribution):
        return {"id": digest([novel.id, key, text])[:24], "source_id": novel.id, "source_title": novel.title,
                "source_revision": str(getattr(novel, "updated_at", "") or ""), "role": role,
                "weight": 1.0 if index == 0 else 0.55, "primary": index == 0,
                "mechanism": text[:650], "adaptation": str(contribution.get("adapt") or "")[:240],
                "evidence_limit": "已存分析卡，不代表核实原著全文"}

    @classmethod
    def retrieve(cls, cards: list[dict], scene: dict, limit=5) -> tuple[list[dict], list[dict]]:
        import json
        query = json.dumps(scene, ensure_ascii=False)
        ranked, rejected = [], []
        for card in cards:
            score = relevance(query, card["mechanism"] + card.get("adaptation", "")) * card["weight"]
            if card["role"] == "voice" and not card["primary"]:
                rejected.append({"card_id": card["id"], "decision": "rejected", "reason": "补充书不覆盖主叙事声音"})
            elif score <= 0:
                rejected.append({"card_id": card["id"], "decision": "rejected", "reason": "与本场功能无检索相关性"})
            else:
                ranked.append((score, card))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        selected = []
        role_counts = {}
        for score, card in ranked:
            if len(selected) < limit and role_counts.get(card["role"], 0) < 2:
                selected.append(card)
                role_counts[card["role"]] = role_counts.get(card["role"], 0) + 1
            else:
                rejected.append({"card_id": card["id"], "decision": "rejected", "reason": "本场机制预算或角色重复"})
        return selected, rejected
