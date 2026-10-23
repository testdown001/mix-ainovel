# AIMETA P=故事骨架倒推规划|R=预切分卷_终局与卷高潮生成_前置条件回填_分块编辑_区间取用|NR=不含蓝图落库|E=StoryBackboneService|X=internal|A=立项质量层|D=llm_service,prompt_service,concept_dossier_service|S=db|RD=./README.ai
"""故事骨架服务：立项书 → 终局 → 各卷高潮 → 回填前置条件（伏笔）。

倒推规划的核心：先定「这本书往哪里去」，再问「要让这个高潮不显得天降，前面必须已经
发生什么」。回填出的前置条件在蓝图设定段落成伏笔、在章纲段按窗口强制埋设。

设计要点（与 concept_dossier_service 同一套约束）：
- 全链路软失败：LLM/解析失败返回 None 并保留既有产物，绝不阻断「立项书→蓝图」主链路。
- 卷区间由服务端**先算好再喂给模型**（_precut_volumes），模型只填内容；这样设定段的
  volumes 一定和骨架对齐，不靠模型自觉。
- 存储形态：novel_projects.concept_dossier JSON 加两个键，零迁移：
  {"backbone": {...}, "backbone_meta": {"generated_at", "source_hash",
   "revised_by_author", "edited_blocks": [...], "edited_at"}}
- 立项书改动后骨架自动重算，但作者改过的块永不被覆盖（edited_blocks 回填）。
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import NovelProject
from pydantic import BaseModel, Field

from ..schemas.concept_dossier import (
    BackboneAlternative,
    BackboneAlternativeSet,
    ClimaxNode,
    SetupRequirement,
    StoryBackbone,
)
from .llm_service import LLMService
from .prompt_service import PromptService

logger = logging.getLogger(__name__)

BACKBONE_ENABLED_KEY = "blueprint.backbone_enabled"
_BACKBONE_MAX_TOKENS = 6144
_ALTERNATIVES_MAX_TOKENS = 3072
_ALTERNATIVES_COUNT = 2
_DEFAULT_TOTAL_CHAPTERS = 300
_MIN_TOTAL_CHAPTERS = 30
_MAX_TOTAL_CHAPTERS = 2000
# 第一次兑现必须落在前 12 章；高潮与最晚埋设章之间至少隔这么多章
_FIRST_PROMISE_MAX_CHAPTER = 12
_PLANT_GAP = 3
_EDITABLE_BLOCKS = ("endgame", "first_promise", "midpoint", "climaxes")

_backbone_locks: Dict[str, asyncio.Lock] = {}
_backbone_locks_guard = asyncio.Lock()


async def _get_backbone_lock(project_id: str) -> asyncio.Lock:
    async with _backbone_locks_guard:
        if project_id not in _backbone_locks:
            _backbone_locks[project_id] = asyncio.Lock()
        return _backbone_locks[project_id]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dossier_hash(dossier: Dict[str, Any]) -> str:
    """立项书内容指纹：骨架随立项书变化而失效的依据。"""
    payload = json.dumps(dossier or {}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 纯函数：篇幅估算 / 分卷预切 / 章号归一化
# ---------------------------------------------------------------------------

_CHAPTER_HINT_RE = re.compile(r"(\d{2,4})\s*章")


def estimate_total_chapters(dossier: Dict[str, Any], history_text: str = "") -> int:
    """从立项书（主要是 notes / 长线承诺）和对话里找篇幅线索，取最大的合理值；找不到回默认。

    期待感承诺里的「前 10 章」「前 50 章」是固定节点，不是篇幅；只在 ≥ _MIN_TOTAL_CHAPTERS
    的候选里取最大值，顺手把它们排除。
    """
    candidates: List[int] = []
    sources = [
        str((dossier or {}).get("notes") or ""),
        str(((dossier or {}).get("anticipation") or {}).get("long_term") or ""),
        history_text or "",
    ]
    for text in sources:
        for match in _CHAPTER_HINT_RE.finditer(text):
            try:
                value = int(match.group(1))
            except ValueError:
                continue
            if _MIN_TOTAL_CHAPTERS <= value <= _MAX_TOTAL_CHAPTERS:
                candidates.append(value)
    if not candidates:
        return _DEFAULT_TOTAL_CHAPTERS
    return max(candidates)


def precut_volumes(total_chapters: int) -> List[Tuple[int, int]]:
    """按篇幅预切 3-6 卷：第一卷短（立足与破局），其余均分。区间首尾相接覆盖 1..total。"""
    total = max(_MIN_TOTAL_CHAPTERS, int(total_chapters))
    if total <= 80:
        count = 3
    elif total <= 200:
        count = 4
    elif total <= 400:
        count = 5
    else:
        count = 6
    # 第一卷约 15%，下限 20 章（短篇按均分下限），上限 60 章
    first_len = min(60, max(min(20, total // count), round(total * 0.15)))
    rest = total - first_len
    rest_count = count - 1
    base, extra = divmod(rest, rest_count)
    ranges: List[Tuple[int, int]] = [(1, first_len)]
    cursor = first_len + 1
    for index in range(rest_count):
        length = base + (1 if index < extra else 0)
        ranges.append((cursor, cursor + length - 1))
        cursor += length
    return ranges


def _clamp(value: Any, low: int, high: int, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def _normalize_setups(setups: List[SetupRequirement], climax_chapter: int) -> List[SetupRequirement]:
    """埋设窗口裁到 [1, 高潮章-_PLANT_GAP]；空名条目丢弃。"""
    latest = max(1, climax_chapter - _PLANT_GAP)
    cleaned: List[SetupRequirement] = []
    for item in setups:
        if not (item.name or "").strip():
            continue
        plant_from = _clamp(item.plant_from, 1, latest, 1)
        plant_to = _clamp(item.plant_to, plant_from, latest, latest)
        cleaned.append(item.model_copy(update={
            "name": item.name.strip(),
            "plant_from": plant_from,
            "plant_to": plant_to,
            "tier": "核心" if "核" in (item.tier or "") else "支线",
        }))
    return cleaned


def normalize_backbone(backbone: StoryBackbone, ranges: List[Tuple[int, int]]) -> StoryBackbone:
    """把模型产出按预切区间归一化：卷序/章号/窗口全部落回合法范围，不信任模型自觉。"""
    total = ranges[-1][1] if ranges else backbone.total_chapters
    data = backbone.model_dump()
    data["total_chapters"] = total

    # 卷高潮：按卷序对齐预切区间，缺的卷补空节点，多的丢弃
    by_index: Dict[int, Dict[str, Any]] = {}
    for raw in data.get("climaxes") or []:
        if not isinstance(raw, dict):
            continue
        try:
            index = int(raw.get("volume_index"))
        except (TypeError, ValueError):
            continue
        if 1 <= index <= len(ranges) and index not in by_index:
            by_index[index] = raw  # 卷序越界的条目丢弃，不挤占别的卷
    climaxes: List[Dict[str, Any]] = []
    for position, (start, end) in enumerate(ranges, start=1):
        raw = by_index.get(position) or {}
        # 高潮落在卷内，且至少给前面留 _PLANT_GAP 章可埋
        low = min(end, start + _PLANT_GAP)
        chapter = _clamp(raw.get("chapter"), low, end, end)
        node = ClimaxNode.model_validate({**raw, "volume_index": position, "chapter": chapter})
        node = node.model_copy(update={"setups": _normalize_setups(node.setups, chapter)})
        climaxes.append(node.model_dump())
    data["climaxes"] = climaxes

    first = ClimaxNode.model_validate(data.get("first_promise") or {})
    first_chapter = _clamp(first.chapter, _PLANT_GAP + 1, _FIRST_PROMISE_MAX_CHAPTER, 8)
    first = first.model_copy(update={
        "volume_index": 0,
        "chapter": first_chapter,
        "setups": _normalize_setups(first.setups, first_chapter),
    })
    data["first_promise"] = first.model_dump()

    midpoint_raw = data.get("midpoint")
    if isinstance(midpoint_raw, dict) and (midpoint_raw.get("event") or "").strip():
        midpoint = ClimaxNode.model_validate(midpoint_raw)
        mid_low = max(_PLANT_GAP + 1, round(total * 0.35))
        mid_high = max(mid_low, round(total * 0.65))
        mid_chapter = _clamp(midpoint.chapter, mid_low, mid_high, round(total / 2))
        midpoint = midpoint.model_copy(update={
            "volume_index": 0,
            "chapter": mid_chapter,
            "setups": _normalize_setups(midpoint.setups, mid_chapter),
        })
        data["midpoint"] = midpoint.model_dump()
    else:
        data["midpoint"] = None

    endgame_setups = [SetupRequirement.model_validate(s) for s in (data.get("endgame") or {}).get("setups") or [] if isinstance(s, dict)]
    data.setdefault("endgame", {})
    data["endgame"]["setups"] = [s.model_dump() for s in _normalize_setups(endgame_setups, total)]
    return StoryBackbone.model_validate(data)


# ---------------------------------------------------------------------------
# 纯函数：给蓝图各段用的投影
# ---------------------------------------------------------------------------

def _node_lines(label: str, node: ClimaxNode, *, with_setups: bool) -> List[str]:
    lines = [f"- {label}（第 {node.chapter} 章）：{node.event}"]
    if node.reversal:
        lines.append(f"  翻转/揭示：{node.reversal}")
    if node.cost:
        lines.append(f"  代价：{node.cost}")
    if node.protagonist_state_after:
        lines.append(f"  高潮后主角状态：{node.protagonist_state_after}")
    if with_setups:
        for setup in node.setups:
            lines.append(
                f"  · 前置条件「{setup.name}」[{setup.tier}]（第 {setup.plant_from}-{setup.plant_to} 章之间埋设）："
                f"{setup.what_must_be_established}"
            )
    return lines


def format_backbone_for_prompt(backbone: Optional[StoryBackbone], *, with_setups: bool = True) -> str:
    """骨架 → 设定段/章纲段的注入文本。空骨架出空串。"""
    if backbone is None:
        return ""
    lines: List[str] = [f"【故事骨架】（终局先定，各卷高潮倒推；全书预计 {backbone.total_chapters} 章）"]
    endgame = backbone.endgame
    if endgame.final_confrontation or endgame.core_answer:
        lines.append(f"- 终局：{endgame.final_confrontation}")
        if endgame.core_answer:
            lines.append(f"  核心冲突的答案：{endgame.core_answer}")
        if endgame.protagonist_becomes:
            lines.append(f"  主角最终成为：{endgame.protagonist_becomes}")
        if endgame.cost:
            lines.append(f"  代价：{endgame.cost}")
        if with_setups:
            for setup in endgame.setups:
                lines.append(
                    f"  · 前置条件「{setup.name}」[{setup.tier}]（第 {setup.plant_from}-{setup.plant_to} 章之间埋设）："
                    f"{setup.what_must_be_established}"
                )
    if backbone.first_promise.event:
        lines.extend(_node_lines("第一次兑现", backbone.first_promise, with_setups=with_setups))
    for node in backbone.climaxes:
        theme = f"「{node.volume_theme}」" if node.volume_theme else ""
        lines.extend(_node_lines(f"第 {node.volume_index} 卷{theme}高潮", node, with_setups=with_setups))
    if backbone.midpoint is not None and backbone.midpoint.event:
        lines.extend(_node_lines("全书中点翻案", backbone.midpoint, with_setups=with_setups))
    return "\n".join(lines) if len(lines) > 1 else ""


def pending_setups_for_range(
    backbone: Optional[StoryBackbone], start: int, end: int
) -> List[Tuple[SetupRequirement, int]]:
    """埋设窗口与 [start, end] 相交的前置条件，附其服务的高潮章号（章纲段按批取用）。"""
    if backbone is None:
        return []
    found: List[Tuple[SetupRequirement, int]] = []
    nodes: List[Tuple[List[SetupRequirement], int]] = [(backbone.first_promise.setups, backbone.first_promise.chapter)]
    if backbone.midpoint is not None:
        nodes.append((backbone.midpoint.setups, backbone.midpoint.chapter))
    nodes.extend((node.setups, node.chapter) for node in backbone.climaxes)
    nodes.append((backbone.endgame.setups, backbone.total_chapters))
    for setups, climax_chapter in nodes:
        for setup in setups:
            if setup.plant_from <= end and setup.plant_to >= start:
                found.append((setup, climax_chapter))
    found.sort(key=lambda pair: (pair[0].plant_from, pair[1]))
    return found


def climaxes_in_range(backbone: Optional[StoryBackbone], start: int, end: int) -> List[ClimaxNode]:
    """落在 [start, end] 内的高潮节点（含第一次兑现与中点），章纲段按批取用。"""
    if backbone is None:
        return []
    nodes: List[ClimaxNode] = [backbone.first_promise]
    if backbone.midpoint is not None:
        nodes.append(backbone.midpoint)
    nodes.extend(backbone.climaxes)
    return sorted(
        (node for node in nodes if node.event and start <= node.chapter <= end),
        key=lambda node: node.chapter,
    )


def format_backbone_batch_constraints(backbone, batch_start: int, batch_end: int) -> str:
    """本批必须埋下的前置条件 + 本批内要兑现的高潮（只给与区间相交的条目，省 token）。"""
    if backbone is None:
        return ""
    parts: List[str] = []
    pending = pending_setups_for_range(backbone, batch_start, batch_end)
    if pending:
        lines = ["【本批必须埋下的前置条件（来自故事骨架，硬约束：对应章的 foreshadowing_ops 必须有 plant，summary 要体现埋设动作）】"]
        for setup, climax_chapter in pending:
            window_from = max(setup.plant_from, batch_start)
            window_to = min(setup.plant_to, batch_end)
            lines.append(
                f"- 「{setup.name}」[{setup.tier}]（第 {window_from}-{window_to} 章之间）："
                f"{setup.what_must_be_established}。服务于第 {climax_chapter} 章。"
                + (f" 浇水提示：{setup.develop_hint}" if setup.develop_hint else "")
            )
        parts.append("\n".join(lines))
    nodes = climaxes_in_range(backbone, batch_start, batch_end)
    if nodes:
        lines = ["【本批内要兑现的高潮（对应章的 foreshadowing_ops 要有相关伏笔的 payoff）】"]
        for node in nodes:
            label = "第一次兑现" if node.volume_index == 0 and node.chapter <= 12 else (
                f"第 {node.volume_index} 卷高潮" if node.volume_index else "中点翻案"
            )
            lines.append(
                f"- 第 {node.chapter} 章 {label}：{node.event}"
                + (f"；翻转：{node.reversal}" if node.reversal else "")
                + (f"；代价：{node.cost}" if node.cost else "")
            )
        parts.append("\n".join(lines))
    return "\n\n".join(parts)



# ---------------------------------------------------------------------------
# 纯函数：与蓝图设定段对账 / 章纲回填覆盖检查（确定性，不信任模型自觉）
# ---------------------------------------------------------------------------

_NAME_STRIP_RE = re.compile(r"[\s「」『』《》【】\[\]()（）\"'“”‘’·、，,。.:：;；!！?？-]+")


def normalize_setup_name(name: Any) -> str:
    """伏笔名归一化：去空白与标点、全角转半角、小写，用于 plant/payoff 对账。"""
    text = str(name or "")
    text = "".join(chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in text)
    return _NAME_STRIP_RE.sub("", text).lower()


def _node_iter(backbone: StoryBackbone) -> List[Tuple[str, ClimaxNode | None, int, List[SetupRequirement]]]:
    """(节点标签, 节点, 高潮章, 前置条件) 四元组，终局节点为 None。"""
    nodes: List[Tuple[str, ClimaxNode | None, int, List[SetupRequirement]]] = [
        ("第一次兑现", backbone.first_promise, backbone.first_promise.chapter, backbone.first_promise.setups)
    ]
    if backbone.midpoint is not None:
        nodes.append(("中点翻案", backbone.midpoint, backbone.midpoint.chapter, backbone.midpoint.setups))
    for node in backbone.climaxes:
        nodes.append((f"第 {node.volume_index} 卷高潮", node, node.chapter, node.setups))
    nodes.append(("终局", None, backbone.total_chapters, backbone.endgame.setups))
    return nodes


def reconcile_settings_with_backbone(
    settings_data: Dict[str, Any],
    backbone: StoryBackbone,
    ranges: List[Tuple[int, int]],
) -> Dict[str, int]:
    """设定段落库前对账（原地修改 settings_data）：

    - volumes 区间与卷数以骨架（作者确认过）为准；模型的卷名/arc_goal 在卷数一致时保留，
      climax_hint 改为骨架高潮事件，整个高潮节点写进 volume["climax"]（落库进 volumes.extra）。
    - 骨架的每条前置条件必须出现在 foreshadowings（按归一化名匹配）；缺的由代码补入，
      模型自己加的伏笔保留。
    返回 {"volumes_rewritten": 0/1, "setups_added": n}。
    """
    stats = {"volumes_rewritten": 0, "setups_added": 0}
    raw_volumes = settings_data.get("volumes")
    model_volumes = [v for v in raw_volumes if isinstance(v, dict)] if isinstance(raw_volumes, list) else []
    same_count = len(model_volumes) == len(ranges)
    volumes: List[Dict[str, Any]] = []
    for index, (start, end) in enumerate(ranges):
        node = backbone.climaxes[index] if index < len(backbone.climaxes) else None
        source = model_volumes[index] if same_count else {}
        name = str(source.get("name") or "").strip()
        if not name:
            theme = (node.volume_theme if node else "") or ""
            name = f"第{index + 1}卷" + (f"·{theme}" if theme else "")
        volume: Dict[str, Any] = {
            "name": name,
            "start_chapter": start,
            "end_chapter": end,
            "arc_goal": str(source.get("arc_goal") or "").strip() or ((node.volume_theme if node else "") or ""),
            "climax_hint": (node.event if node and node.event else str(source.get("climax_hint") or "").strip()),
        }
        if node is not None and node.event:
            volume["climax"] = {
                "chapter": node.chapter,
                "event": node.event,
                "reversal": node.reversal,
                "cost": node.cost,
                "protagonist_state_after": node.protagonist_state_after,
            }
        volumes.append(volume)
    if [(v.get("start_chapter"), v.get("end_chapter")) for v in model_volumes] != [(s, e) for s, e in ranges]:
        stats["volumes_rewritten"] = 1
    settings_data["volumes"] = volumes

    raw_fs = settings_data.get("foreshadowings")
    foreshadowings: List[Dict[str, Any]] = [f for f in raw_fs if isinstance(f, dict)] if isinstance(raw_fs, list) else []
    existing = {normalize_setup_name(f.get("name")) for f in foreshadowings}
    for label, _node, climax_chapter, setups in _node_iter(backbone):
        for setup in setups:
            key = normalize_setup_name(setup.name)
            if not key or key in existing:
                continue
            existing.add(key)
            foreshadowings.append({
                "name": setup.name,
                "description": setup.what_must_be_established,
                "planted_chapter": setup.plant_from,
                "target_chapter": climax_chapter,
                "tier": "核心" if setup.tier == "核心" else "支线",
                "type": "setup",
                "reveal_method": setup.develop_hint or f"在{label}（第 {climax_chapter} 章）兑现",
                "reveal_impact": setup.why_needed,
                "related_characters": [],
                "related_plots": [label],
            })
            stats["setups_added"] += 1
    settings_data["foreshadowings"] = foreshadowings
    return stats


class SetupCoverageEntry(BaseModel):
    name: str = ""
    tier: str = "支线"
    plant_from: int = 1
    plant_to: int = 1
    climax_chapter: int = 1
    serves: str = ""
    planted: bool = False
    planted_in: Optional[int] = None
    payoff: bool = False
    via: str = Field(default="ops", description="ops=按 foreshadowing_ops 判定 / summary=按摘要提名退化判定")


class SetupCoverageReport(BaseModel):
    """章纲对骨架前置条件的回填覆盖：确定性计算，审稿门与前端都读它。"""

    total: int = 0
    planted: int = 0
    core_total: int = 0
    core_planted: int = 0
    entries: List[SetupCoverageEntry] = Field(default_factory=list)
    retried: bool = False

    @property
    def ratio(self) -> float:
        return (self.planted / self.total) if self.total else 1.0

    def missing(self, *, core_only: bool = False) -> List[SetupCoverageEntry]:
        return [e for e in self.entries if not e.planted and (e.tier == "核心" or not core_only)]

    def to_prompt(self) -> str:
        lines = [
            f"【骨架前置条件回填覆盖（代码核对，以此为准打 foreshadowing_payoff）】"
            f"已埋 {self.planted}/{self.total}（核心 {self.core_planted}/{self.core_total}）"
        ]
        for entry in self.entries:
            state = f"已在第 {entry.planted_in} 章埋下" if entry.planted else "未埋"
            payoff = "，高潮章有兑现" if entry.payoff else "，高潮章无兑现操作"
            lines.append(
                f"- 「{entry.name}」[{entry.tier}] 窗口第 {entry.plant_from}-{entry.plant_to} 章，"
                f"服务{entry.serves}（第 {entry.climax_chapter} 章）：{state}{payoff}"
            )
        return "\n".join(lines)


def setup_coverage(
    backbone: Optional[StoryBackbone],
    outline_items: List[Dict[str, Any]],
    *,
    limit_chapter: Optional[int] = None,
) -> Optional[SetupCoverageReport]:
    """逐条核对前置条件：窗口内某章 foreshadowing_ops 含 plant（或退化为摘要提到伏笔名）。

    limit_chapter：只核对窗口起点 ≤ 该章号的条目（章纲只排到第 N 章时，后面的窗口不算缺）。
    无骨架返回 None。
    """
    if backbone is None:
        return None
    by_number: Dict[int, Dict[str, Any]] = {int(item["chapter_number"]): item for item in outline_items}
    max_chapter = limit_chapter if limit_chapter is not None else (max(by_number) if by_number else 0)
    report = SetupCoverageReport()
    for label, _node, climax_chapter, setups in _node_iter(backbone):
        for setup in setups:
            if setup.plant_from > max_chapter:
                continue
            key = normalize_setup_name(setup.name)
            entry = SetupCoverageEntry(
                name=setup.name, tier=setup.tier, plant_from=setup.plant_from,
                plant_to=min(setup.plant_to, max_chapter), climax_chapter=climax_chapter, serves=label,
            )
            for number in range(setup.plant_from, min(setup.plant_to, max_chapter) + 1):
                item = by_number.get(number)
                if item is None:
                    continue
                ops = ((item.get("planning") or {}).get("foreshadowing_ops") or [])
                if any(o.get("op") == "plant" and normalize_setup_name(o.get("name")) == key for o in ops if isinstance(o, dict)):
                    entry.planted, entry.planted_in, entry.via = True, number, "ops"
                    break
                if not ops and key and key in normalize_setup_name(item.get("summary")):
                    entry.planted, entry.planted_in, entry.via = True, number, "summary"
                    break
            climax_item = by_number.get(climax_chapter)
            if climax_item is not None:
                ops = ((climax_item.get("planning") or {}).get("foreshadowing_ops") or [])
                entry.payoff = any(
                    o.get("op") == "payoff" and normalize_setup_name(o.get("name")) == key
                    for o in ops if isinstance(o, dict)
                ) or (not ops and bool(key) and key in normalize_setup_name(climax_item.get("summary")))
            report.entries.append(entry)
            report.total += 1
            report.planted += int(entry.planted)
            if entry.tier == "核心":
                report.core_total += 1
                report.core_planted += int(entry.planted)
    return report


def spoiler_guards(backbone: Optional[StoryBackbone]) -> List[str]:
    """宪法 forbidden_content 用的防剧透条目：各卷翻转与终局在落章之前不得揭示。"""
    if backbone is None:
        return []
    items: List[str] = []
    for node in backbone.climaxes:
        if node.reversal.strip():
            items.append(f"防剧透：第 {node.chapter} 章之前不得揭示「{node.reversal.strip()[:60]}」")
    if backbone.midpoint is not None and backbone.midpoint.reversal.strip():
        items.append(f"防剧透：第 {backbone.midpoint.chapter} 章之前不得揭示「{backbone.midpoint.reversal.strip()[:60]}」")
    endgame = backbone.endgame
    for text in (endgame.core_answer, endgame.final_confrontation):
        if text.strip():
            items.append(f"防剧透：终局前不得提前交代「{text.strip()[:60]}」")
            break
    return items


# ---------------------------------------------------------------------------
# 服务
# ---------------------------------------------------------------------------

class StoryBackboneService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)

    @staticmethod
    def get_state(project: NovelProject) -> Dict[str, Any]:
        state = project.concept_dossier
        return dict(state) if isinstance(state, dict) else {}

    @staticmethod
    def read_backbone(state: Dict[str, Any]) -> Optional[StoryBackbone]:
        raw = state.get("backbone")
        if not isinstance(raw, dict):
            return None
        try:
            return StoryBackbone.model_validate(raw)
        except Exception:  # noqa: BLE001 - 坏数据按无骨架处理
            return None

    @staticmethod
    def is_stale(state: Dict[str, Any]) -> bool:
        """立项书在骨架生成后被改过。"""
        meta = state.get("backbone_meta")
        dossier = state.get("dossier")
        if not isinstance(meta, dict) or not isinstance(dossier, dict):
            return False
        return meta.get("source_hash") != dossier_hash(dossier)

    @staticmethod
    def ranges_for(state: Dict[str, Any], backbone: StoryBackbone) -> List[Tuple[int, int]]:
        """生成时记录的预切卷区间（蓝图对账用）。"""
        meta = state.get("backbone_meta") if isinstance(state.get("backbone_meta"), dict) else {}
        return _meta_ranges(meta, backbone)

    async def is_enabled(self) -> bool:
        from .blueprint_review_service import read_blueprint_switch

        return await read_blueprint_switch(self.session, BACKBONE_ENABLED_KEY, True)

    # ------------------------------------------------------------------
    # 主入口：确保骨架就绪；幂等，软失败
    # ------------------------------------------------------------------
    async def ensure_backbone(
        self, project_id: str, user_id: int, *, force: bool = False
    ) -> Dict[str, Any]:
        lock = await _get_backbone_lock(project_id)
        async with lock:
            project = await self.session.get(NovelProject, project_id)
            if project is None:
                return {}
            state = self.get_state(project)
            dossier = state.get("dossier")
            if not isinstance(dossier, dict):
                return state
            if not await self.is_enabled():
                return state

            meta = state.get("backbone_meta") if isinstance(state.get("backbone_meta"), dict) else {}
            existing = self.read_backbone(state)
            if existing is not None and not force:
                if not self.is_stale(state):
                    return state
                if meta.get("revised_by_author"):
                    # 作者改过的骨架不自动重算，响应层标 stale 交作者决定
                    return state

            generated = await self._generate(project, dossier, user_id)
            if generated is None:
                return state
            if existing is not None and meta.get("edited_blocks"):
                generated = _restore_edited_blocks(generated, existing, meta.get("edited_blocks") or [])

            state["backbone"] = generated.model_dump()
            state["backbone_meta"] = {
                "generated_at": _now_iso(),
                "source_hash": dossier_hash(dossier),
                "ranges": [[start, end] for start, end in precut_volumes(generated.total_chapters)],
                "revised_by_author": bool(meta.get("edited_blocks")),
                "edited_blocks": list(meta.get("edited_blocks") or []),
            }
            project.concept_dossier = dict(state)
            await self.session.commit()
            logger.info(
                "项目 %s 故事骨架就绪：%d 卷，%d 条前置条件",
                project_id, len(generated.climaxes), len(generated.all_setups()),
            )
            return state

    # ------------------------------------------------------------------
    # 分块编辑（确认页 PATCH）
    # ------------------------------------------------------------------
    async def patch_backbone(self, project: NovelProject, partial: Dict[str, Any]) -> Dict[str, Any]:
        state = self.get_state(project)
        raw = copy.deepcopy(state.get("backbone") or {})
        if not raw:
            raise ValueError("骨架尚未生成")
        meta = dict(state.get("backbone_meta") or {})
        edited = list(meta.get("edited_blocks") or [])

        for key, value in (partial or {}).items():
            if key not in _EDITABLE_BLOCKS:
                continue
            if key == "climaxes":
                if not isinstance(value, dict):
                    continue
                nodes = raw.get("climaxes") or []
                for index_key, node_patch in value.items():
                    try:
                        index = int(index_key)
                    except (TypeError, ValueError):
                        continue
                    if not (1 <= index <= len(nodes)) or not isinstance(node_patch, dict):
                        continue
                    nodes[index - 1] = {**nodes[index - 1], **node_patch, "volume_index": index}
                    _mark(edited, f"climaxes.{index}")
                raw["climaxes"] = nodes
            elif key == "midpoint" and value is None:
                raw["midpoint"] = None
                _mark(edited, "midpoint")
            elif isinstance(value, dict):
                raw[key] = {**(raw.get(key) or {}), **value}
                _mark(edited, key)

        backbone = StoryBackbone.model_validate(raw)  # 非法值在这里抛，路由转 400
        backbone = normalize_backbone(backbone, _meta_ranges(meta, backbone))
        state["backbone"] = backbone.model_dump()
        meta.update({"revised_by_author": True, "edited_blocks": edited, "edited_at": _now_iso()})
        state["backbone_meta"] = meta
        project.concept_dossier = dict(state)
        await self.session.commit()
        return state

    # ------------------------------------------------------------------
    # 备选终局（阶段四）：高温出 N 个方向 → 作者选一个 → 以它为锚点重新倒推
    # ------------------------------------------------------------------
    async def generate_alternatives(self, project: NovelProject, user_id: int) -> List[Dict[str, Any]]:
        """生成备选方向并存进 state["backbone_alternatives"]；失败返回 []（不动既有骨架）。"""
        state = self.get_state(project)
        dossier = state.get("dossier")
        current = self.read_backbone(state)
        if not isinstance(dossier, dict) or current is None:
            return []
        try:
            system_prompt = await self.prompt_service.get_prompt("story_backbone_alternatives")
            if not system_prompt:
                logger.warning("项目 %s 备选终局跳过：缺少 story_backbone_alternatives 提示词", project.id)
                return []
            from .concept_dossier_service import format_dossier_for_prompt

            ranges = self.ranges_for(state, current)
            parts = [
                format_dossier_for_prompt(dossier) or "【故事立项书】（空）",
                "【现方案（备选必须在终局走向上与之本质不同）】\n" + format_backbone_for_prompt(current, with_setups=False),
                f"【分卷（不得更改）】共 {len(ranges)} 卷：" + "；".join(
                    f"第 {i} 卷 第 {a}-{b} 章" for i, (a, b) in enumerate(ranges, start=1)
                ) + f"\n请给出 {_ALTERNATIVES_COUNT} 个备选方向，每个 climax_events 恰好 {len(ranges)} 条。",
            ]
            exclusions = (project.exclusions or "").strip()
            if exclusions:
                parts.append(f"【创作禁区】\n{exclusions}")
            result = await self.llm_service.generate_structured(
                prompt="\n\n".join(parts),
                schema=BackboneAlternativeSet,
                system_prompt=system_prompt,
                temperature=0.9,
                user_id=user_id,
                max_tokens=_ALTERNATIVES_MAX_TOKENS,
                default=None,
            )
            if result is None:
                return []
            items: List[Dict[str, Any]] = []
            for index, alt in enumerate(result.alternatives[:4], start=1):
                if not (alt.endgame.final_confrontation or "").strip():
                    continue
                alt = alt.model_copy(update={
                    "id": f"alt-{index}",
                    "climax_events": [str(e).strip() for e in alt.climax_events][: len(ranges)],
                })
                items.append(alt.model_dump())
            if not items:
                return []
            state["backbone_alternatives"] = {"items": items, "generated_at": _now_iso()}
            project.concept_dossier = dict(state)
            await self.session.commit()
            logger.info("项目 %s 备选终局生成 %d 个", project.id, len(items))
            return items
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("项目 %s 备选终局生成失败: %s", project.id, exc)
            return []

    @staticmethod
    def list_alternatives(state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        raw = state.get("backbone_alternatives")
        if not isinstance(raw, dict):
            return [], None
        items = [i for i in (raw.get("items") or []) if isinstance(i, dict)]
        return items, raw.get("generated_at")

    async def apply_alternative(
        self, project_id: str, user_id: int, alternative_id: str
    ) -> Optional[Dict[str, Any]]:
        """以作者选定的备选方向为锚点重新倒推（补前置条件）；失败返回 None 并保留原骨架。"""
        lock = await _get_backbone_lock(project_id)
        async with lock:
            project = await self.session.get(NovelProject, project_id)
            if project is None:
                return None
            state = self.get_state(project)
            dossier = state.get("dossier")
            items, _ = self.list_alternatives(state)
            chosen = next((i for i in items if i.get("id") == alternative_id), None)
            if not isinstance(dossier, dict) or chosen is None:
                return None
            try:
                alt = BackboneAlternative.model_validate(chosen)
            except Exception:  # noqa: BLE001
                return None
            anchor_lines = [
                "【作者选定的终局方向（必须照此倒推，只补前置条件与细节，不得改走向）】",
                f"- 方向：{alt.label}" if alt.label else "",
                f"- 最后一战：{alt.endgame.final_confrontation}",
                f"- 冲突的答案：{alt.endgame.core_answer}" if alt.endgame.core_answer else "",
                f"- 主角成为：{alt.endgame.protagonist_becomes}" if alt.endgame.protagonist_becomes else "",
                f"- 代价：{alt.endgame.cost}" if alt.endgame.cost else "",
                f"- 中点翻案：{alt.midpoint_event}" if alt.midpoint_event else "",
            ]
            anchor_lines.extend(f"- 第 {i} 卷高潮：{event}" for i, event in enumerate(alt.climax_events, start=1) if event)
            generated = await self._generate(
                project, dossier, user_id, anchor="\n".join(line for line in anchor_lines if line)
            )
            if generated is None:
                return None
            edited = ["endgame"] + [f"climaxes.{i}" for i in range(1, len(generated.climaxes) + 1)]
            state["backbone"] = generated.model_dump()
            state["backbone_meta"] = {
                "generated_at": _now_iso(),
                "source_hash": dossier_hash(dossier),
                "ranges": [[start, end] for start, end in precut_volumes(generated.total_chapters)],
                "revised_by_author": True,  # 作者选的方向：立项书再改也不自动推翻
                "edited_blocks": edited,
                "chosen_alternative": alt.label or alternative_id,
            }
            state.pop("backbone_alternatives", None)
            project.concept_dossier = dict(state)
            await self.session.commit()
            logger.info("项目 %s 已采用备选终局「%s」并重新倒推", project_id, alt.label or alternative_id)
            return state

    # ------------------------------------------------------------------
    # 内部：生成
    # ------------------------------------------------------------------
    async def _generate(
        self, project: NovelProject, dossier: Dict[str, Any], user_id: int, *, anchor: str = ""
    ) -> Optional[StoryBackbone]:
        try:
            system_prompt = await self.prompt_service.get_prompt("story_backbone")
            if not system_prompt:
                logger.warning("项目 %s 故事骨架跳过：缺少 story_backbone 提示词", project.id)
                return None

            from .concept_dossier_service import format_dossier_for_prompt

            total = estimate_total_chapters(dossier)
            ranges = precut_volumes(total)
            parts = [format_dossier_for_prompt(dossier) or "【故事立项书】（空）"]
            if anchor.strip():
                parts.append(anchor.strip())

            state = self.get_state(project)
            stress = state.get("stress_report")
            if isinstance(stress, dict):
                high = [
                    f"- {p.get('issue', '')}：{p.get('reason', '')}"
                    for p in stress.get("toxic_points") or []
                    if isinstance(p, dict) and "高" in str(p.get("severity") or "")
                ]
                if high:
                    parts.append("【压力推演点名的高危毒点（终局与高潮设计必须绕开）】\n" + "\n".join(high))

            exclusions = (project.exclusions or "").strip()
            if exclusions:
                parts.append(f"【创作禁区（任何节点不得触碰）】\n{exclusions}")

            structure = await self._structure_reference(project)
            if structure:
                parts.append("【参考小说的结构手法（只参考节奏思路，情节必须原创）】\n" + structure)

            range_lines = "\n".join(
                f"- 第 {index} 卷：第 {start}-{end} 章" for index, (start, end) in enumerate(ranges, start=1)
            )
            parts.append(
                f"【篇幅与分卷（服务端已定，不得更改）】\n全书预计 {total} 章，分 {len(ranges)} 卷：\n{range_lines}\n"
                f"climaxes 必须恰好 {len(ranges)} 条，volume_index 依次为 1..{len(ranges)}，"
                f"每条 chapter 落在该卷区间内（通常在卷末附近）。first_promise.chapter ≤ {_FIRST_PROMISE_MAX_CHAPTER}。"
                f"每条前置条件的 plant_to 必须比它服务的高潮章至少早 {_PLANT_GAP} 章。total_chapters 填 {total}。"
            )

            backbone = await self.llm_service.generate_structured(
                prompt="\n\n".join(parts),
                schema=StoryBackbone,
                system_prompt=system_prompt,
                temperature=0.5,
                user_id=user_id,
                max_tokens=_BACKBONE_MAX_TOKENS,
                default=None,
            )
            if backbone is None:
                return None
            if not (backbone.endgame.final_confrontation or "").strip() and not backbone.climaxes:
                logger.warning("项目 %s 故事骨架产物无终局也无卷高潮，按失败处理", project.id)
                return None
            backbone = normalize_backbone(backbone, ranges)
            thin = [node.volume_index for node in backbone.climaxes if len(node.setups) < 3]
            if thin:
                logger.warning("项目 %s 故事骨架：第 %s 卷前置条件少于 3 条（不补造）", project.id, thin)
            return backbone
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("项目 %s 故事骨架生成失败（不阻断主链路）: %s", project.id, exc)
            return None

    async def _structure_reference(self, project: NovelProject) -> str:
        try:
            from .blueprint_generation_service import _build_structure_reference

            return await _build_structure_reference(self.session, project)
        except Exception as exc:  # noqa: BLE001 - 参考是增益不是依赖
            logger.debug("项目 %s 骨架结构参考注入失败(已忽略): %s", project.id, exc)
            return ""


def _mark(edited: List[str], block: str) -> None:
    if block not in edited:
        edited.append(block)


def _meta_ranges(meta: Dict[str, Any], backbone: StoryBackbone) -> List[Tuple[int, int]]:
    """生成时记在 backbone_meta.ranges 的预切区间；缺失（旧数据）时按 total 重切。"""
    raw = meta.get("ranges")
    if isinstance(raw, list) and len(raw) == len(backbone.climaxes):
        try:
            return [(int(pair[0]), int(pair[1])) for pair in raw]
        except (TypeError, ValueError, IndexError):
            pass
    return precut_volumes(backbone.total_chapters)


def _restore_edited_blocks(
    generated: StoryBackbone, previous: StoryBackbone, edited_blocks: List[str]
) -> StoryBackbone:
    """重算后把作者改过的块从旧骨架搬回来。"""
    data = generated.model_dump()
    old = previous.model_dump()
    for block in edited_blocks:
        if block in ("endgame", "first_promise", "midpoint"):
            data[block] = old.get(block)
        elif block.startswith("climaxes."):
            try:
                index = int(block.split(".", 1)[1])
            except ValueError:
                continue
            if 1 <= index <= len(old.get("climaxes") or []) and index <= len(data.get("climaxes") or []):
                data["climaxes"][index - 1] = old["climaxes"][index - 1]
    try:
        return StoryBackbone.model_validate(data)
    except Exception:  # noqa: BLE001 - 回填失败用新产物
        return generated


async def background_ensure_backbone(project_id: str, user_id: int) -> None:
    """立项书就绪后的后台骨架生成入口（自带会话，绝不外抛）。"""
    from ..db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            await StoryBackboneService(session).ensure_backbone(project_id, user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("项目 %s 后台故事骨架生成失败: %s", project_id, exc)
