# AIMETA P=白金写作上下文_节奏伏笔钩子|R=生成章节前控制信息|NR=仅伏笔embedding不含正文LLM|E=platinum_context|X=internal|A=写作控制|D=sqlalchemy|S=db|RD=./README.ai
"""Shared context builders for high-quality webnovel chapter generation."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.foreshadowing import Foreshadowing
from ..models.novel import ChapterOutline
from .foreshadowing_service import ForeshadowingService

PLATINUM_WRITING_BRIEF_FALLBACK = """
你是起点白金作家级别的长篇连载写手，请严格执行：
1. 先服从本章功能与已规划的情绪曲线，完成有意义的剧情、关系或认知变化；压迫、破局、余波、关系、日常、揭秘各有自己的节奏。
2. 信息与情绪按人物经历展开，关键选择有因有果；允许松弛、沉默和留白，不按固定字数插入刺激，不统一规定对白比例或趣味点。
3. 伏笔必须可追踪：老伏笔要有进展，新伏笔要可兑现，避免空泛悬念。
4. 角色行动先于解释：通过选择、代价、后果塑造人物，而不是口头总结。
5. 允许本章小问题完整解决，结尾可落在动作、台词、决定或兑现后的余波上；让仍成立的长线期待延续，不强制新危机或硬断章。
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

FORESHADOW_OVERDUE_BASE_CHAPTERS = 20  # 埋设超期基线；长篇按 total//5 放宽


def overdue_age_threshold(total_chapters: Optional[int]) -> int:
    """埋设超期阈值：随总章数缩放 max(20, total//5)；拿不到 total 时保持基线 20。"""
    if not total_chapters or total_chapters <= 0:
        return FORESHADOW_OVERDUE_BASE_CHAPTERS
    return max(FORESHADOW_OVERDUE_BASE_CHAPTERS, total_chapters // 5)


async def resolve_total_chapters(session: AsyncSession, project_id: str) -> Optional[int]:
    """取项目大纲总章数（overdue 阈值缩放用）；查询失败/无大纲返回 None（调用方降级基线）。"""
    try:
        result = await session.execute(
            select(func.count())
            .select_from(ChapterOutline)
            .where(ChapterOutline.project_id == project_id)
        )
        total = int(result.scalar() or 0)
        return total if total > 0 else None
    except Exception:
        return None


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
    chapter_function = _mission_value(chapter_mission, ("chapter_function", "chapter_type"))

    lines = [
        f"章节进度：第 {chapter_number}/{safe_total} 章（约 {progress}%）",
        f"阶段判定：{stage_name}",
        f"全书阶段目标（长线参考）：{stage_goal}",
        f"阶段节奏示意（仅供参考，不是本章配额）：{rhythm_ratio}",
        f"本章功能：{chapter_function or '按章纲与人物处境确定，不默认冲突升级章'}",
        f"本章主节拍：{macro_beat or '未指定（按大纲执行单一主节拍）'}",
        f"叙事视角：{pov or '未指定（保持单视角稳定）'}",
        "优先规则：本章功能与已规划的情绪曲线、松弛点、留白优先于全书阶段配比；选择本章相关的线索推进，不要求每章同时推进三条线。",
        "功能节奏：压迫章写清暂不能反击的理由；破局章兑现准备；余波章承接得失与代价；关系章改变亲疏；日常章建立牵挂；揭秘章改变旧理解。",
        "执行要求：让剧情、关系或认知产生有因有果的变化；对白、趣味与转折按场景需要安排，不设统一比例、次数或字数间隔。",
        f"本章锚点：标题《{outline_title}》；核心任务={_truncate(outline_summary, 80)}",
    ]

    # 题材参数只提供跨章参考，不能覆盖本章功能与情感设计。
    if genre_pacing_config:
        q_ratio = genre_pacing_config.get("quest_ratio", 0.6)
        f_ratio = genre_pacing_config.get("fire_ratio", 0.25)
        c_ratio = genre_pacing_config.get("constellation_ratio", 0.15)
        max_buildup = genre_pacing_config.get("max_buildup_chapters", 3)
        lines.append(f"题材长线节奏参考：Quest={q_ratio:.0%} / Fire={f_ratio:.0%} / Constellation={c_ratio:.0%}；不作为本章篇幅或刺激配额")
        lines.append(f"蓄力检查窗口：约 {max_buildup} 章后检查长期承诺是否有进展；按因果兑现，不强制本章出爆点")

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
    ending_style = _mission_value(chapter_mission, ("chapter_end_style",))

    tail_hint = _truncate(previous_tail or previous_summary, 120)
    lines = [
        f"上章承接线索：{tail_hint or '无历史章节，首章按章纲建立人物处境与阅读期待'}",
        f"本章需承接的问题：{carry_hook or '承接上章尚未完成的行动、问题或情绪后果，按因果回应，不跳过关键结果'}",
        "中段推进：服从本章功能，让行动、关系或认知产生变化；余波和关系场景允许停顿，不强制受阻或代价升级。",
        f"本章结尾设计：{ending_hook or ending_style or '可停在具体行动、关系变化或兑现后的余波上，让已有长线期待自然延续'}",
        "连载规则：旧承诺要有回声，新增悬念要可兑现；允许局部闭环，不为留钩强加新危机、打断道歉或切掉胜利后的余韵。",
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
    total_chapters = await resolve_total_chapters(session, project_id)

    ranked: List[Tuple[int, List[str], Foreshadowing]] = []
    for item in unresolved:
        score, reasons = _score_foreshadowing(item, chapter_number, total_chapters)
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


def _score_foreshadowing(
    item: Foreshadowing,
    chapter_number: int,
    total_chapters: Optional[int] = None,
) -> Tuple[int, List[str]]:
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
        if age >= overdue_age_threshold(total_chapters):
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
    if not isinstance(chapter_mission, dict):
        return None
    # 与任务书保持同样优先级，兼容新式分层 Mission 与历史扁平 Mission。
    for source in (
        chapter_mission.get("hard_constraints"),
        chapter_mission.get("soft_suggestions"),
        chapter_mission,
    ):
        if not isinstance(source, dict):
            continue
        for key in keys:
            value = source.get(key)
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
