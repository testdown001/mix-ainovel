# AIMETA P=章级规划落盘|R=规划字段提取_映射chapter_blueprints_批量替换与单章upsert|NR=不含LLM调用|E=extract_planning_from_item,replace_chapter_blueprints,upsert_chapter_blueprint|X=internal|A=章级规划|D=chapter_blueprint模型|S=db|RD=./README.ai
"""章级剧情规划落盘：补上 chapter_blueprints 表缺失的写入方。

章纲生成（蓝图 Stage B / 写作台续排）产出的章级规划字段（chapter_function /
hook_type / coolpoint / foreshadowing_ops / must_not_include）在这里统一：
1. 从 LLM 单章条目里提取清洗（extract_planning_from_item）；
2. 映射到 chapter_blueprints 的既有字段（map_planning_to_blueprint_fields）；
3. 落库（蓝图全量替换 replace_chapter_blueprints / 续排单章 upsert_chapter_blueprint）。

落库即激活两个既有读取方：validate_coolpoint_rhythm 节奏校验（不再因表空空转）
与任务书生成的 load_chapter_blueprint 约束来源。
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_blueprint import ChapterBlueprint

logger = logging.getLogger(__name__)

# 章节功能：中文标签（LLM 输出）→ ChapterFunction 枚举值（读取方按枚举值判定）
CHAPTER_FUNCTION_MAP: Dict[str, str] = {
    "铺垫": "buildup",
    "爽点": "climax",
    "高潮": "climax",
    "转折": "turning",
    "揭示": "revelation",
    "过渡": "interlude",
    "推进": "progression",
    "收束": "resolution",
}
_VALID_FUNCTIONS = {
    "progression", "turning", "revelation", "buildup", "climax", "resolution", "interlude",
}

# 悬念密度按章节功能推导（SuspenseDensity 枚举语义见模型注释）
_FUNCTION_TO_DENSITY: Dict[str, str] = {
    "climax": "compact",
    "turning": "explosive",
    "revelation": "explosive",
    "buildup": "gradual",
    "progression": "gradual",
    "resolution": "gradual",
    "interlude": "relaxed",
}

# 认知颠覆等级按功能推导：转折/揭示是反转章（≥3 即被节奏校验计为爽点章）
_FUNCTION_TO_TWIST: Dict[str, int] = {
    "turning": 4,
    "revelation": 4,
    "climax": 3,
}

_VALID_FS_OPS = {"plant", "develop", "payoff"}
# develop 在 chapter_blueprints.foreshadowing_ops 的既有枚举里叫 reinforce
_FS_OP_STORE_MAP = {"plant": "plant", "develop": "reinforce", "payoff": "payoff"}


def _clean_str(value: Any, limit: int = 200) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _clean_str_list(value: Any, limit: int = 8) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned: List[str] = []
    for item in value:
        text = _clean_str(item, 120)
        if text:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def extract_planning_from_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从章纲单章条目提取章级规划字段（清洗归一，全缺返回 None）。"""
    if not isinstance(item, dict):
        return None
    planning: Dict[str, Any] = {}

    function = _clean_str(item.get("chapter_function"), 32)
    if function:
        planning["chapter_function"] = function

    hook = _clean_str(item.get("hook_type"), 64)
    if hook:
        planning["hook_type"] = hook

    coolpoint = _clean_str(item.get("coolpoint"), 300)
    if coolpoint:
        planning["coolpoint"] = coolpoint

    raw_ops = item.get("foreshadowing_ops")
    if isinstance(raw_ops, dict):
        raw_ops = [raw_ops]
    if isinstance(raw_ops, list):
        ops: List[Dict[str, str]] = []
        for entry in raw_ops:
            if isinstance(entry, str):
                # 兼容 "plant:身世玉佩" 简写
                if ":" in entry or "：" in entry:
                    sep = ":" if ":" in entry else "："
                    op_text, name_text = entry.split(sep, 1)
                    entry = {"op": op_text, "name": name_text}
                else:
                    continue
            if not isinstance(entry, dict):
                continue
            op = _clean_str(entry.get("op"), 16).lower()
            name = _clean_str(entry.get("name") or entry.get("foreshadowing"), 120)
            if op in _VALID_FS_OPS and name:
                ops.append({"op": op, "name": name})
        if ops:
            planning["foreshadowing_ops"] = ops[:6]

    must_not = _clean_str_list(item.get("must_not_include"))
    if must_not:
        planning["must_not_include"] = must_not

    return planning or None


def normalize_chapter_function(raw: str) -> Optional[str]:
    """中文标签/英文枚举 → ChapterFunction 枚举值；识别不出返回 None。"""
    text = (raw or "").strip().lower()
    if not text:
        return None
    if text in _VALID_FUNCTIONS:
        return text
    return CHAPTER_FUNCTION_MAP.get((raw or "").strip())


def map_planning_to_blueprint_fields(planning: Dict[str, Any]) -> Dict[str, Any]:
    """规划字段 → chapter_blueprints 列值（只产出规划相关列，不含状态列）。"""
    fields: Dict[str, Any] = {}
    function = normalize_chapter_function(planning.get("chapter_function") or "")
    if function:
        fields["chapter_function"] = function
        fields["suspense_density"] = _FUNCTION_TO_DENSITY.get(function, "gradual")
        fields["cognitive_twist_level"] = _FUNCTION_TO_TWIST.get(function, 1)

    hook = planning.get("hook_type")
    if isinstance(hook, str) and hook.strip():
        fields["suspense_type"] = hook.strip()[:128]

    coolpoint = planning.get("coolpoint")
    if isinstance(coolpoint, str) and coolpoint.strip():
        fields["brief_summary"] = coolpoint.strip()

    ops = planning.get("foreshadowing_ops")
    if isinstance(ops, list) and ops:
        stored_ops: List[str] = []
        names: List[str] = []
        for entry in ops:
            if not isinstance(entry, dict):
                continue
            stored = _FS_OP_STORE_MAP.get(entry.get("op") or "")
            if stored and stored not in stored_ops:
                stored_ops.append(stored)
            name = entry.get("name")
            if isinstance(name, str) and name.strip() and name.strip() not in names:
                names.append(name.strip())
        if stored_ops:
            fields["foreshadowing_ops"] = ",".join(stored_ops)[:128]
        if names:
            fields["involved_foreshadowings"] = names

    must_not = planning.get("must_not_include")
    if isinstance(must_not, list) and must_not:
        fields["mission_constraints"] = {"must_not_include": list(must_not)}

    if fields:
        fields["extra"] = {"planning": planning}
    return fields


async def replace_chapter_blueprints(
    session: AsyncSession,
    project_id: str,
    outlines: List[Dict[str, Any]],
) -> int:
    """蓝图全量替换时的批量落盘：清空项目全部规划行后按新章纲重建（不提交，随调用方事务）。

    outlines 元素形如 {"chapter_number": int, "planning": Optional[dict]}——章号必须是
    重排后的最终章号（number_map 已应用），保证与 chapter_outlines 严格对齐。
    """
    await session.execute(
        delete(ChapterBlueprint).where(ChapterBlueprint.project_id == project_id)
    )
    # executemany 要求各行键集合一致：规划列固定成同一模板，缺的字段填默认值
    row_template: Dict[str, Any] = {
        "suspense_density": "gradual",
        "foreshadowing_ops": None,
        "cognitive_twist_level": 1,
        "chapter_function": None,
        "suspense_type": None,
        "involved_foreshadowings": None,
        "mission_constraints": None,
        "brief_summary": None,
        "extra": None,
    }
    rows: List[Dict[str, Any]] = []
    for outline in outlines:
        planning = outline.get("planning")
        if not isinstance(planning, dict) or not planning:
            continue
        fields = map_planning_to_blueprint_fields(planning)
        if not fields:
            continue
        row = dict(row_template)
        row.update(fields)
        row["project_id"] = project_id
        row["chapter_number"] = int(outline["chapter_number"])
        rows.append(row)
    if rows:
        await session.execute(ChapterBlueprint.__table__.insert(), rows)
    return len(rows)


async def upsert_chapter_blueprint(
    session: AsyncSession,
    project_id: str,
    chapter_number: int,
    planning: Optional[Dict[str, Any]],
) -> None:
    """续排/重排单章的规划落盘：只更新规划列，保留 is_generated/is_finalized/quality_score
    等状态列（不提交，随调用方事务）。planning 为空时不动既有行。"""
    if not isinstance(planning, dict) or not planning:
        return
    fields = map_planning_to_blueprint_fields(planning)
    if not fields:
        return
    result = await session.execute(
        select(ChapterBlueprint).where(
            ChapterBlueprint.project_id == project_id,
            ChapterBlueprint.chapter_number == chapter_number,
        ).order_by(ChapterBlueprint.id.asc())
    )
    row = result.scalars().first()
    if row is None:
        session.add(ChapterBlueprint(
            project_id=project_id,
            chapter_number=chapter_number,
            **fields,
        ))
        return
    for key, value in fields.items():
        setattr(row, key, value)
