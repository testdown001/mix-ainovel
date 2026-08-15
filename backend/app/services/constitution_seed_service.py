# AIMETA P=小说宪法自动播种|R=蓝图落库后组装NovelConstitution_毒点禁区题材禁忌进forbidden_content|NR=不含宪法CRUD与注入|E=seed_constitution_from_blueprint|X=internal|A=宪法播种|D=constitution模型|S=db|RD=./README.ai
"""小说宪法自动播种：蓝图落库后从蓝图/立项书/推演报告/创作禁区组装 NovelConstitution。

- 纯代码组装（零 LLM 成本、确定性）：宪法的质量来自源数据（蓝图与推演本身已过质量门）。
- 幂等：项目已有宪法则不覆盖（管理员/用户手工配置优先）。
- 播种即生效：`[小说宪法](必须遵守)` 注入链路与六维评审的 forbidden_content 快扫已全通，
  反向约束从第 1 章起贯穿正文生成。
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.constitution import NovelConstitution

logger = logging.getLogger(__name__)

# 题材禁忌：按题材关键词命中追加（读者用脚投票验证过的弃书点，非风格偏好）
_GENRE_TABOOS: List[tuple] = [
    (("爽文", "都市", "重生", "赘婿"), [
        "主角连续多章被动挨打、只积累屈辱不还手",
        "爽点承诺跳票：铺垫拉满却不给兑现",
    ]),
    (("仙侠", "玄幻", "修真", "武侠"), [
        "境界/力量体系前后矛盾（同境界战力忽高忽低）",
        "越级战斗无铺垫无代价，赢得毫无说服力",
    ]),
    (("言情", "恋爱", "婚恋"), [
        "用双方一句话就能解开的强行误会推动剧情",
        "感情线工具人化：恋爱对象没有独立目标与立场",
    ]),
    (("悬疑", "推理", "刑侦"), [
        "侦探视角作弊：对读者隐藏主角已经看到的关键线索",
        "真相靠凶手主动自白而非推理链闭合",
    ]),
    (("系统", "游戏", "网游"), [
        "系统喧宾夺主替主角做所有决定，主角沦为执行器",
    ]),
]

# 全题材通用禁忌（主流读者公认毒点）
_UNIVERSAL_TABOOS: List[str] = [
    "主角圣母式原谅仇人且不给充分理由",
    "配角集体智商下线来衬托主角",
    "重要转折靠无铺垫的巧合堆砌",
]

_MAX_FORBIDDEN_ITEMS = 18


def _split_exclusions(exclusions: str) -> List[str]:
    """用户禁区文本 → 条目列表（按换行/分号切，保留原话）。"""
    items: List[str] = []
    for chunk in (exclusions or "").replace("；", "\n").replace(";", "\n").split("\n"):
        text = chunk.strip().strip("、-· ")
        if text and text not in items:
            items.append(text[:120])
    return items


def _genre_taboos(genre: str) -> List[str]:
    taboos: List[str] = []
    for keywords, items in _GENRE_TABOOS:
        if any(keyword in (genre or "") for keyword in keywords):
            taboos.extend(items)
    return taboos


def build_forbidden_content(
    *,
    exclusions: str,
    stress_report: Optional[Dict[str, Any]],
    genre: str,
) -> List[str]:
    """forbidden_content = 用户创作禁区 + 推演高危毒点 + 题材禁忌 + 通用禁忌（去重限长）。"""
    items: List[str] = []

    for text in _split_exclusions(exclusions):
        items.append(f"用户禁区：{text}")

    if isinstance(stress_report, dict):
        for point in stress_report.get("toxic_points") or []:
            if not isinstance(point, dict):
                continue
            if "高" not in (point.get("severity") or ""):
                continue
            issue = (point.get("issue") or "").strip()
            fix = (point.get("fix_suggestion") or point.get("reason") or "").strip()
            if issue:
                entry = f"高危毒点：{issue}" + (f"（{fix[:80]}）" if fix else "")
                items.append(entry[:160])

    items.extend(_genre_taboos(genre))
    items.extend(_UNIVERSAL_TABOOS)

    deduped: List[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped[:_MAX_FORBIDDEN_ITEMS]


async def seed_constitution_from_blueprint(
    session: AsyncSession,
    *,
    project_id: str,
    blueprint_data: Dict[str, Any],
    dossier: Optional[Dict[str, Any]] = None,
    stress_report: Optional[Dict[str, Any]] = None,
    exclusions: str = "",
) -> bool:
    """蓝图落库后播种宪法。已有宪法不覆盖；成功播种返回 True（不提交，随调用方事务）。"""
    existing = (
        await session.execute(
            select(NovelConstitution).where(NovelConstitution.project_id == project_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("项目 %s 已有小说宪法，跳过自动播种（幂等）", project_id)
        return False

    dossier = dossier if isinstance(dossier, dict) else {}
    genre = str(blueprint_data.get("genre") or dossier.get("genre") or "")

    core_theme = str(
        dossier.get("core_selling_line") or blueprint_data.get("one_sentence_summary") or ""
    )[:255]
    core_conflict = str(dossier.get("core_conflict") or "")[:255]
    anticipation = dossier.get("anticipation") if isinstance(dossier.get("anticipation"), dict) else {}
    story_direction = str(anticipation.get("long_term") or "")[:255]

    world_setting = blueprint_data.get("world_setting")
    world_rules: Optional[Dict[str, Any]] = None
    if isinstance(world_setting, dict) and world_setting.get("core_rules"):
        world_rules = {"core_rules": world_setting["core_rules"]}

    power_system_text = ""
    golden_finger = blueprint_data.get("golden_finger")
    if isinstance(golden_finger, dict) and (golden_finger.get("name") or "").strip():
        parts = [str(golden_finger.get("name") or "")]
        for key, label in (("description", "机制"), ("limitations", "限制与代价"), ("growth_potential", "成长空间")):
            value = golden_finger.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{label}：{value.strip()}")
        power_system_text = "；".join(parts)

    pov_character = ""
    protagonist = dossier.get("protagonist") if isinstance(dossier.get("protagonist"), dict) else {}
    if protagonist.get("name"):
        pov_character = str(protagonist["name"])[:255]
    elif isinstance(blueprint_data.get("characters"), list) and blueprint_data["characters"]:
        first = blueprint_data["characters"][0]
        if isinstance(first, dict):
            pov_character = str(first.get("name") or "")[:255]

    constitution = NovelConstitution(
        project_id=project_id,
        core_theme=core_theme or None,
        genre=genre[:128] or None,
        core_conflict=core_conflict or None,
        story_direction=story_direction or None,
        pov_type="第三人称有限视角（跟随主角）",
        pov_character=pov_character or None,
        overall_tone=str(blueprint_data.get("tone") or "")[:128] or None,
        language_style=str(blueprint_data.get("style") or "")[:128] or None,
        world_type=genre[:128] or None,
        power_system=power_system_text or None,
        world_rules=world_rules,
        forbidden_content=build_forbidden_content(
            exclusions=exclusions, stress_report=stress_report, genre=genre
        ),
        twist_frequency="每2-3章一个小爽点或小钩子，8-12章一个中爆点，20-30章一个大爆点",
        foreshadowing_rules=(
            "伏笔埋设后必须在蓝图标注的目标章兑现或明确推进；"
            "长线伏笔每 20 章内至少回响一次，禁止长期失联后突兀兑现。"
        ),
        extra={"seeded_by": "blueprint", "seeded_at": datetime.now(timezone.utc).isoformat()},
    )
    session.add(constitution)
    logger.info(
        "项目 %s 小说宪法自动播种完成：forbidden_content=%d 条",
        project_id, len(constitution.forbidden_content or []),
    )
    return True
