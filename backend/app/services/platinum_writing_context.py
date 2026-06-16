# AIMETA P=白金写作上下文_节奏伏笔钩子|R=生成章节前控制信息|NR=仅伏笔embedding不含正文LLM|E=platinum_context|X=internal|A=写作控制|D=sqlalchemy|S=db|RD=./README.ai
"""Shared context builders for high-quality webnovel chapter generation."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.foreshadowing import Foreshadowing
from .foreshadowing_service import ForeshadowingService

PLATINUM_WRITING_BRIEF_FALLBACK = """
你是起点白金作家级别的长篇连载写手，请严格执行：
1. 每章必须完成「推进主线 + 放大冲突 + 留下追更钩子」三件事，禁止只做氛围描写。
2. 信息投放遵循“七分已知、三分未知”：读者每章获得新信息，但保留关键缺口。
3. 伏笔必须可追踪：老伏笔要有进展，新伏笔要可兑现，避免空泛悬念。
4. 角色行动先于解释：通过选择、代价、后果塑造人物，而不是口头总结。
5. 结尾钩子必须具体：明确“谁在下一章面临什么不可回避的问题”。
""".strip()

_TYPE_LABELS = {
    "question": "疑问伏笔",
    "mystery": "谜团伏笔",
    "hint": "暗示伏笔",
    "clue": "线索伏笔",
    "setup": "铺垫伏笔",
}

_IMPORTANCE_WEIGHT = {
    "major": 4,
    "minor": 2,
    "subtle": 1,
}


def build_platinum_rhythm_brief(
    *,
    chapter_number: int,
    total_chapters: int,
    outline_title: str,
    outline_summary: str,
    chapter_mission: Optional[Dict[str, Any]] = None,
    genre_pacing_config: Optional[Dict[str, Any]] = None,
    strand_info: Optional[Any] = None,
) -> str:
    """Build chapter rhythm guidance inspired by serialized webnovel pacing."""
    stage_name, rhythm_ratio, stage_goal = _resolve_stage(chapter_number, total_chapters)
    safe_total = max(total_chapters, chapter_number, 1)
    progress = min(100, int(chapter_number / safe_total * 100))
    macro_beat = _mission_value(chapter_mission, ("macro_beat", "beat", "chapter_beat"))
    pov = _mission_value(chapter_mission, ("pov", "pov_character"))

    lines = [
        f"章节进度：第 {chapter_number}/{safe_total} 章（约 {progress}%）",
        f"阶段判定：{stage_name}",
        f"阶段目标：{stage_goal}",
        f"推荐节奏配比：{rhythm_ratio}",
        f"本章主节拍：{macro_beat or '未指定（按大纲执行单一主节拍）'}",
        f"叙事视角：{pov or '未指定（保持单视角稳定）'}",
        "执行要求：Quest 线推进一步，Fire 线抬升冲突一次，Constellation 线补一枚长线信号。",
        f"本章锚点：标题《{outline_title}》；核心任务={_truncate(outline_summary, 80)}",
    ]

    # 题材节奏配置覆盖
    if genre_pacing_config:
        q_ratio = genre_pacing_config.get("quest_ratio", 0.6)
        f_ratio = genre_pacing_config.get("fire_ratio", 0.25)
        c_ratio = genre_pacing_config.get("constellation_ratio", 0.15)
        max_buildup = genre_pacing_config.get("max_buildup_chapters", 3)
        lines.append(f"题材节奏覆盖：Quest={q_ratio:.0%} / Fire={f_ratio:.0%} / Constellation={c_ratio:.0%}")
        lines.append(f"蓄力上限：连续 {max_buildup} 章后必须出爆点")

    # 线团信息注入
    if strand_info:
        from .strand_weave_service import StrandWeaveService
        lines.append(StrandWeaveService.build_strand_prompt(strand_info))

    return "\n".join(lines)


def build_hook_continuity_brief(
    *,
    previous_summary: str,
    previous_tail: str,
    chapter_mission: Optional[Dict[str, Any]] = None,
) -> str:
    """Build hook continuity instructions between adjacent chapters."""
    carry_hook = _mission_value(
        chapter_mission,
        ("carry_over_hook", "carry_hook", "suspense", "core_suspense", "continuity_hook"),
    )
    ending_hook = _mission_value(chapter_mission, ("ending_hook", "tail_hook", "next_hook"))

    tail_hint = _truncate(previous_tail or previous_summary, 120)
    lines = [
        f"上章尾钩线索：{tail_hint or '无历史章节，首章可直接制造主悬念'}",
        f"本章需承接的问题：{carry_hook or '开章前 20% 必须回应上章悬念，不可跳过'}",
        "中段加压：至少出现一次“目标受阻或代价升级”，避免平铺推进。",
        f"本章结尾新钩：{ending_hook or '结尾抛出具体冲突（人物/利益/时限三要素至少两项）'}",
        "连载规则：旧钩要有回声，新钩要可兑现，不做纯烟雾弹。",
    ]
    return "\n".join(lines)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """纯 Python 余弦相似度；维度不匹配或零向量返回 0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def _semantic_foreshadowing_scores(
    llm_service: Any,
    query_text: str,
    items: Sequence[Foreshadowing],
) -> Dict[int, float]:
    """计算各未回收伏笔与当前章节语境的语义相似度 {伏笔id: 0-1}。

    embedding 通道不可用 / 无 query / 调用失败 / 维度异常时一律返回 {}，
    调用方据此退回纯启发式排序（降级不报错，零破坏现有行为）。
    """
    query_text = (query_text or "").strip()
    if llm_service is None or not query_text or not items:
        return {}
    texts: List[str] = [query_text]
    id_order: List[int] = []
    for it in items:
        body = ((it.content or "") or (it.name or "")).strip()
        if not body:
            continue
        texts.append(body[:512])
        id_order.append(it.id)
    if not id_order:
        return {}
    try:
        embeddings = await llm_service.get_embeddings_batch(texts)
    except Exception:
        return {}
    if not embeddings or len(embeddings) != len(texts):
        return {}
    query_vec = embeddings[0]
    return {fid: _cosine(query_vec, vec) for fid, vec in zip(id_order, embeddings[1:])}


async def build_foreshadowing_urgency_brief(
    *,
    session: AsyncSession,
    project_id: str,
    chapter_number: int,
    top_k: int = 6,
    query_text: Optional[str] = None,
    llm_service: Any = None,
) -> str:
    """Rank unresolved foreshadowings and format actionable writing hints.

    当提供 query_text(当前章节大纲)与 llm_service 时，叠加「伏笔内容 vs 本章语境」的
    语义相关性加权排序；embedding 不可用则自动降级为纯启发式（紧迫度/逾期/埋设时长）。
    """
    service = ForeshadowingService(session)
    unresolved = await service.get_unresolved_foreshadowings(project_id, chapter_number)
    if not unresolved:
        return "当前没有未回收伏笔。本章可新增 1-2 个短线伏笔，并确保可在 3-8 章内兑现。"

    semantic_scores = await _semantic_foreshadowing_scores(llm_service, query_text or "", unresolved)

    ranked: List[Tuple[int, List[str], Foreshadowing]] = []
    for item in unresolved:
        score, reasons = _score_foreshadowing(item, chapter_number)
        sim = semantic_scores.get(item.id)
        if sim and sim > 0:
            sem_points = round(sim * 10)  # 语义相关性加成(0-10)，与紧迫度同量级但不喧宾夺主
            if sem_points > 0:
                score += sem_points
                if sim >= 0.5:
                    reasons = [f"与本章大纲高度相关(语义{sim:.2f})，优先在本章呼应", *reasons]
        ranked.append((score, reasons[:3], item))
    ranked.sort(key=lambda row: row[0], reverse=True)

    chosen = ranked[: max(1, top_k)]
    lines = [f"未回收伏笔共 {len(unresolved)} 个，建议优先处理以下 {len(chosen)} 个："]
    for idx, (score, reasons, item) in enumerate(chosen, start=1):
        name = _resolve_foreshadowing_name(item)
        fs_type = _TYPE_LABELS.get((item.type or "").lower(), item.type or "伏笔")
        target = f"目标回收章={item.target_reveal_chapter}" if item.target_reveal_chapter else "目标回收章=未设置"
        characters = _format_related_characters(item.related_characters)
        lines.append(f"{idx}. {name}（{fs_type}）| 紧迫分 {score} | {target}{characters}")
        lines.append(f"   建议：{'; '.join(reasons)}")
    return "\n".join(lines)


def _resolve_stage(chapter_number: int, total_chapters: int) -> Tuple[str, str, str]:
    safe_total = max(total_chapters, chapter_number, 1)
    ratio = chapter_number / safe_total
    if ratio <= 0.30:
        return (
            "Quest 起盘段（开局立题）",
            "开头钩子15% / 推进45% / 爆点25% / 尾钩15%",
            "快速确立主问题、敌我张力和读者追更理由",
        )
    if ratio <= 0.75:
        return (
            "Fire 扩燃段（中盘升压）",
            "开头钩子8% / 推进52% / 爆点32% / 尾钩8%",
            "让冲突升级并形成连锁后果，避免原地踏步",
        )
    return (
        "Constellation 收束段（后盘兑付）",
        "开头钩子6% / 推进44% / 爆点35% / 尾钩15%",
        "集中回收高价值伏笔，同时打开下一卷入口",
    )


def _score_foreshadowing(item: Foreshadowing, chapter_number: int) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    urgency = int(item.urgency or 0)
    score += urgency
    if urgency >= 8:
        reasons.append("紧迫度很高，本章最好推进到可验证信息")
    elif urgency >= 5:
        reasons.append("紧迫度中高，本章至少给出实质进展")

    importance_weight = _IMPORTANCE_WEIGHT.get((item.importance or "").lower(), 1)
    score += importance_weight
    if item.importance:
        reasons.append(f"{item.importance} 级伏笔，不宜长期搁置")

    if item.target_reveal_chapter:
        delta = item.target_reveal_chapter - chapter_number
        if delta < 0:
            overdue = abs(delta)
            score += 6 + min(overdue, 8)
            reasons.append(f"已逾期 {overdue} 章，需尽快回收或转化")
        elif delta == 0:
            score += 6
            reasons.append("本章就是目标回收章，必须兑现关键价值")
        elif delta <= 2:
            score += 4 - delta
            reasons.append(f"{delta} 章内到期，立即加强铺垫")

    if item.chapter_number:
        age = max(0, chapter_number - item.chapter_number)
        if age >= 20:
            score += 4
            reasons.append(f"已埋设 {age} 章，读者记忆风险高")
        elif age >= 10:
            score += 2

    if not reasons:
        reasons.append("维持存在感：本章至少补一条可追踪线索")
    return score, reasons[:3]


def _resolve_foreshadowing_name(item: Foreshadowing) -> str:
    if item.name:
        return _truncate(item.name, 30)
    if item.content:
        return _truncate(item.content.replace("\n", " "), 30)
    return f"伏笔#{item.id}"


def _format_related_characters(related_characters: Optional[Sequence[Any]]) -> str:
    if not related_characters:
        return ""
    first_two = [str(value) for value in list(related_characters)[:2] if value]
    if not first_two:
        return ""
    return f"，相关角色：{', '.join(first_two)}"


def _mission_value(chapter_mission: Optional[Dict[str, Any]], keys: Sequence[str]) -> Optional[str]:
    if not chapter_mission:
        return None
    for key in keys:
        value = chapter_mission.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _truncate(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[:limit].rstrip()}..."
