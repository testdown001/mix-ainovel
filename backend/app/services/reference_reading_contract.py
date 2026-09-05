# AIMETA P=参考小说阅读动力契约|R=融合模式_素材压缩_跨阶段指导|NR=不调用LLM|E=FusionDNA|X=internal|A=纯函数|D=pydantic|S=none
"""One narrative voice, complementary reading mechanisms, and honest evidence boundaries."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

VERSION = 2


class ReaderLoop(BaseModel):
    model_config = ConfigDict(extra="ignore")
    desire: str = Field(min_length=1, max_length=200, description="读者为什么替人物在意")
    promise: str = Field(min_length=1, max_length=200, description="读者等待的具体变化")
    pressure: str = Field(min_length=1, max_length=200, description="有进展的阻力、代价与信息差")
    payoff: str = Field(min_length=1, max_length=200, description="靠人物选择兑现什么，不能只拖延")
    aftereffect: str = Field(min_length=1, max_length=200, description="兑现如何改变关系或处境并产生后续牵挂")


class ReferenceContribution(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    source: str = Field(alias="from", min_length=1, max_length=100)
    take: str = Field(min_length=1, max_length=220)
    adapt: str = Field(min_length=1, max_length=220)
    role: str = Field(min_length=1, max_length=120, description="此书在统一方案中的主要分工")
    evidence: str = Field(min_length=1, max_length=220, description="依据哪项资料；资料不足须明确说明")


class FusionDNA(BaseModel):
    model_config = ConfigDict(extra="ignore")
    narrative_strategy: str = Field(min_length=1, max_length=500)
    style_fingerprint: str = Field(min_length=1, max_length=400)
    reader_loop: ReaderLoop
    structure_references: list[ReferenceContribution] = Field(min_length=1, max_length=3)
    conflict_resolution: list[str] = Field(min_length=1, max_length=4)
    blended_pacing: str = Field(min_length=1, max_length=400)
    dialogue_style: str = Field(min_length=1, max_length=300)
    scene_rhythm: str = Field(min_length=1, max_length=300)
    avoidance_list: list[str] = Field(min_length=1, max_length=6)
    key_techniques: list[str] = Field(min_length=1, max_length=5)
    evidence_limits: str = Field(min_length=1, max_length=300)


def _text(value: Any, limit: int = 180) -> str:
    if isinstance(value, list):
        value = "；".join(str(item) for item in value[:3])
    return str(value or "").strip()[:limit]


def source_signature(novels: list) -> str:
    materials = [
        {key: getattr(novel, key, None) for key in
         ("id", "title", "outline_content", "memory_card", "beat_library", "style_guide")}
        for novel in novels
    ]
    return hashlib.sha256(json.dumps(materials, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def is_current(dna: Any, novels: list, expected_ids: list | None = None) -> bool:
    ids = [getattr(n, "id", None) for n in novels]
    return bool(
        novels and isinstance(dna, dict) and dna.get("version") == VERSION
        and dna.get("source_ids") == ids
        and (expected_ids is None or ids == list(dict.fromkeys(expected_ids))[:3])
        and dna.get("source_signature") == source_signature(novels)
    )


def stamp(dna: dict, novels: list, *, generated: bool) -> dict:
    return {**dna, "version": VERSION, "source_ids": [getattr(n, "id", None) for n in novels],
            "source_signature": source_signature(novels), "generation_status": "ready" if generated else "fallback"}


def fusion_materials(novels: list) -> str:
    """Budget by semantic field so later books and payoff/voice fields cannot be cut off."""
    blocks = []
    for novel in novels[:3]:
        card = getattr(novel, "memory_card", None) or {}
        guide = getattr(novel, "style_guide", None) or {}
        library = getattr(novel, "beat_library", None) or {}
        material = {
            "title": novel.title,
            "outline": _text(getattr(novel, "outline_content", ""), 450),
            "reading_mechanisms": {k: _text(card.get(k)) for k in (
                "core_selling_point", "main_conflict_pattern", "reader_expectation", "payoff_rhythm",
                "relationship_pull", "cool_point_patterns", "emotion_control_pattern", "pacing_traits", "risks")},
            "voice": {k: _text(v, 120) for k, v in guide.items()},
            "structure": {k: _text(v, 180) for k, v in (library.get("structure") or {}).items()},
            "beats": [{k: _text(beat.get(k), 120) for k in ("situation", "setup", "turn", "payoff", "pitfalls")}
                      for beat in (library.get("beats") or [])[:3]],
        }
        # AI imitation passages are not evidence of the source book's real prose.
        blocks.append(json.dumps(material, ensure_ascii=False))
    return "\n\n".join(blocks)


def fallback_dna(novels: list) -> dict:
    """Grounded provisional directions, explicitly not a completed model synthesis."""
    if not novels:
        return {}
    contributions = []
    for index, novel in enumerate(novels[:3]):
        card = getattr(novel, "memory_card", None) or {}
        take = _text(card.get("main_conflict_pattern") or card.get("core_selling_point") or card.get("takeaways"))
        contributions.append({"from": novel.title, "role": "主要阅读期待" if index == 0 else "补充阅读动力",
                              "take": take or "资料不足，暂不推断该书技法",
                              "adapt": "转成当前人物的目标、选择与后果；与已确认设定冲突时舍弃",
                              "evidence": "现有创作记忆卡" if take else "资料不足"})
    card = getattr(novels[0], "memory_card", None) or {}
    guide = getattr(novels[0], "style_guide", None) or {}
    voice = "；".join(_text(guide.get(k), 100) for k in
                    ("narrative_pov", "sentence_rhythm", "dialogue_style", "emotion_expression") if guide.get(k))
    return stamp({
        "narrative_strategy": "暂按各书已有分析分配阅读动力；围绕本书同一条人物因果线组合，避免分章轮换原作套路。",
        "style_fingerprint": voice or "沿用本书已确认的视角、叙述语气和人物声线",
        "structure_references": contributions,
        "reader_loop": {
            "desire": _text(card.get("relationship_pull")) or "先让读者在意人物想保住什么、失去会怎样",
            "promise": _text(card.get("reader_expectation") or card.get("core_selling_point")) or "提出可感知、值得等待的目标或关系变化",
            "pressure": _text(card.get("main_conflict_pattern")) or "阻力中给予新进展，代价来自人物选择，不靠反复误会拖延",
            "payoff": _text(card.get("payoff_rhythm")) or "兑现已经铺垫的一部分期待，让能力、证据或关系发生实际变化",
            "aftereffect": "给兑现留下情绪余波，再由改变后的处境生出下一份牵挂",
        },
        "blended_pacing": _text(card.get("pacing_traits")) or "按当前章功能安排蓄势、进展、兑现或余波，不规定固定高潮间隔",
        "dialogue_style": _text(guide.get("dialogue_style") or card.get("dialogue_style")),
        "scene_rhythm": _text(card.get("emotion_control_pattern")),
        "conflict_resolution": ["本书设定与人物声线优先；补充参考只贡献适用机制，不改变叙事人称或每章切换文风"],
        "avoidance_list": ["不复刻原作角色、专有设定、标志性事件链和句子"],
        "key_techniques": ["铺垫必须改变读者预期，兑现必须改变人物处境；安静的关系进展也可以构成回报"],
        "evidence_limits": "临时参考方案，尚未完成模型融合；依据已有分析，不能当作已读完整原著的结论。",
    }, novels, generated=False)


def format_contract(dna: dict, max_chars: int = 2700) -> str:
    if not dna:
        return ""
    lines = ["本书设定、章纲、人物声线优先；参考提供写作机制，不增加既定剧情。"]
    if dna.get("generation_status") == "fallback":
        lines.append("【融合状态】临时参考方案，完整融合尚未就绪。")
    for key, label, cap in (("narrative_strategy", "组合逻辑", 200), ("style_fingerprint", "统一叙事声音", 240)):
        if dna.get(key):
            lines.append(f"【{label}】{_text(dna[key], cap)}")
    for ref in (dna.get("structure_references") or [])[:3]:
        lines.append(f"【《{_text(ref.get('from'), 32)}》分工】{_text(ref.get('role'), 40)}："
                     f"{_text(ref.get('take'), 95)}；转译：{_text(ref.get('adapt'), 75)}")
    loop = dna.get("reader_loop") or {}
    for key, label in (("desire", "人物牵挂"), ("promise", "读者期待"), ("pressure", "蓄势与进展"),
                       ("payoff", "兑现"), ("aftereffect", "情绪余波与后续牵挂")):
        if loop.get(key):
            lines.append(f"【{label}】{_text(loop[key], 110)}")
    lines.append("【本章执行】依章纲判断本章承担铺垫、推进、兑现或余波中的哪一环；每场只完成自己的变化，"
                 "不把整套循环硬塞进每章，不为断章扣住应当兑现的答案。")
    for key, label in (("conflict_resolution", "冲突取舍"), ("blended_pacing", "节奏"),
                       ("dialogue_style", "对白"), ("scene_rhythm", "场景"),
                       ("avoidance_list", "避免复刻"), ("evidence_limits", "依据边界")):
        if dna.get(key):
            lines.append(f"【{label}】{_text(dna[key], 110)}")
    return "\n".join(lines)[:max_chars]


def project_contract(novels: list, dna: Any, expected_ids: list | None = None) -> str:
    if not novels:
        return ""
    current = is_current(dna, novels, expected_ids)
    text = format_contract(dna if current else fallback_dna(novels))
    if expected_ids and len(novels) != len(set(expected_ids)):
        text = "【参考资料未齐】仅使用已就绪资料，尚未完成全部参考融合。\n" + text
    return text
