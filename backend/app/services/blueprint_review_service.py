# AIMETA P=蓝图审稿门|R=商业量表评审_定向修订重问_滚动章纲轻量审稿|NR=不含蓝图生成与落库|E=BlueprintReviewService|X=internal|A=蓝图质量门|D=llm_service,prompt_service|S=db|RD=./README.ai
"""蓝图审稿门：两段生成完成后、落库前，用商业网文量表审一遍蓝图+章纲。

- 总开关 `blueprint.review_enabled`（默认 true）：关了则审稿/修订整段跳过。
- 低于阈值（SystemConfig `blueprint.review_min_score`，默认 70）且
  `blueprint.review_auto_revise`（默认 true）→ 定向修订重问：
  只重写被点名的设定块 / 章号区间，合并回原蓝图，最多 1 轮，随后复审一次更新分数。
- 仍不达标不硬阻断：照常落库，审稿报告透传给前端让用户决策。
- 全链路软失败：审稿/修订任何一步失败都跳过该步，绝不让蓝图生成挂掉。
"""
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.concept_dossier import BlueprintReviewReport
from ..utils.json_utils import parse_llm_json, remove_think_tags
from .llm_service import LLMService
from .prompt_service import PromptService

logger = logging.getLogger(__name__)

REVIEW_MIN_SCORE_KEY = "blueprint.review_min_score"
REVIEW_MIN_SCORE_DEFAULT = 70
REVIEW_ENABLED_KEY = "blueprint.review_enabled"
REVIEW_AUTO_REVISE_KEY = "blueprint.review_auto_revise"
STRESS_ENABLED_KEY = "blueprint.stress_enabled"
_REVIEW_MAX_TOKENS = 4096
_REVISION_MAX_TOKENS = 8192


def parse_config_bool(value: Optional[str], default: bool = True) -> bool:
    """SystemConfig 布尔值：缺省/空串回 default；识别 1/true/yes/on。"""
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


async def read_blueprint_switch(session: AsyncSession, key: str, default: bool = True) -> bool:
    """读取蓝图相关布尔开关；配置缺失或读取失败回 default（质量优先）。"""
    try:
        from .config_service import ConfigService

        record = await ConfigService(session).get_config(key)
        if record is not None:
            return parse_config_bool(record.value, default)
    except Exception:  # noqa: BLE001 - 配置读取失败回默认
        pass
    return default

# 定向修订允许改写的设定块白名单（与 blueprint_review.md 的 target 约定一致）
_REVISABLE_SETTINGS_KEYS = {
    "title",
    "one_sentence_summary",
    "full_synopsis",
    "world_setting",
    "golden_finger",
    "characters",
    "volumes",
    "foreshadowings",
}


def _outline_lines(outline_items: List[Dict[str, Any]], limit_chars: int = 24000) -> str:
    """章纲压缩为审稿输入：一章一行，带章级规划字段。"""
    lines: List[str] = []
    for item in outline_items:
        planning = item.get("planning") if isinstance(item.get("planning"), dict) else {}
        extras: List[str] = []
        if planning.get("chapter_function"):
            extras.append(f"功能={planning['chapter_function']}")
        if planning.get("hook_type"):
            extras.append(f"钩子={planning['hook_type']}")
        if planning.get("coolpoint"):
            extras.append(f"爽点={planning['coolpoint']}")
        ops = planning.get("foreshadowing_ops")
        if isinstance(ops, list) and ops:
            ops_text = "、".join(
                f"{op.get('op', '')}:{op.get('name', '')}" for op in ops if isinstance(op, dict)
            )
            if ops_text:
                extras.append(f"伏笔={ops_text}")
        extra_text = f"（{'；'.join(extras)}）" if extras else ""
        lines.append(
            f"第{item['chapter_number']}章《{item.get('title', '')}》{extra_text}：{item.get('summary', '')}"
        )
    text = "\n".join(lines)
    if len(text) > limit_chars:
        text = text[:limit_chars] + "\n……（超长截断）"
    return text


def parse_chapter_range(target: str) -> Optional[Tuple[int, int]]:
    """"chapters:5-8" → (5, 8)；解析失败返回 None。"""
    if not isinstance(target, str) or not target.startswith("chapters:"):
        return None
    body = target.split(":", 1)[1].strip()
    try:
        if "-" in body:
            lo_text, hi_text = body.split("-", 1)
            lo, hi = int(lo_text), int(hi_text)
        else:
            lo = hi = int(body)
    except (TypeError, ValueError):
        return None
    if lo < 1 or hi < lo:
        return None
    return lo, hi


class BlueprintReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)

    async def get_min_score(self) -> int:
        try:
            from .config_service import ConfigService

            record = await ConfigService(self.session).get_config(REVIEW_MIN_SCORE_KEY)
            if record and record.value:
                return max(0, min(100, int(record.value)))
        except Exception:  # noqa: BLE001 - 配置读取失败回默认
            pass
        return REVIEW_MIN_SCORE_DEFAULT

    async def is_review_enabled(self) -> bool:
        return await read_blueprint_switch(self.session, REVIEW_ENABLED_KEY, True)

    async def is_auto_revise_enabled(self) -> bool:
        return await read_blueprint_switch(self.session, REVIEW_AUTO_REVISE_KEY, True)

    # ------------------------------------------------------------------
    # 评审
    # ------------------------------------------------------------------
    async def review(
        self,
        *,
        settings_data: Dict[str, Any],
        outline_items: List[Dict[str, Any]],
        stress_report: Optional[Dict[str, Any]],
        dossier: Optional[Dict[str, Any]],
        user_id: int,
    ) -> Optional[BlueprintReviewReport]:
        """全量审稿（蓝图+章纲）。失败或总开关关闭返回 None（跳过审稿门）。"""
        try:
            if not await self.is_review_enabled():
                logger.info("蓝图审稿跳过：blueprint.review_enabled=false")
                return None
            system_prompt = await self.prompt_service.get_prompt("blueprint_review")
            if not system_prompt:
                logger.warning("蓝图审稿跳过：缺少 blueprint_review 提示词")
                return None

            slim_settings = {
                k: settings_data.get(k)
                for k in (
                    "title", "genre", "style", "tone", "target_audience",
                    "one_sentence_summary", "full_synopsis", "world_setting",
                    "golden_finger", "volumes", "foreshadowings",
                )
                if settings_data.get(k) is not None
            }
            parts = [
                "【蓝图设定】\n" + json.dumps(slim_settings, ensure_ascii=False, indent=1),
                "【逐章章纲】\n" + _outline_lines(outline_items),
            ]
            if isinstance(dossier, dict) and isinstance(dossier.get("anticipation"), dict):
                parts.append(
                    "【立项书期待感承诺（核对兑现路径）】\n"
                    + json.dumps(dossier["anticipation"], ensure_ascii=False)
                )
            if isinstance(stress_report, dict) and stress_report.get("toxic_points"):
                parts.append(
                    "【立项阶段压力推演毒点清单（复查是否已修掉）】\n"
                    + json.dumps(stress_report["toxic_points"], ensure_ascii=False, indent=1)
                )

            report = await self.llm_service.generate_structured(
                prompt="\n\n".join(parts),
                schema=BlueprintReviewReport,
                system_prompt=system_prompt,
                temperature=0.3,
                user_id=user_id,
                max_tokens=_REVIEW_MAX_TOKENS,
                default=None,
            )
            logger.info(
                "蓝图审稿完成：total=%d issues=%d", report.total_score, len(report.issues)
            )
            return report
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("蓝图审稿失败（跳过审稿门）: %s", exc)
            return None

    # ------------------------------------------------------------------
    # 定向修订：设定块
    # ------------------------------------------------------------------
    async def revise_settings_blocks(
        self,
        *,
        settings_data: Dict[str, Any],
        report: BlueprintReviewReport,
        user_id: int,
        exclusions: str = "",
    ) -> Dict[str, Any]:
        """只重写被点名的设定块，合并回原设定；失败返回原设定。"""
        issues = report.issues_for_settings()
        if not issues:
            return settings_data
        block_names: Set[str] = set()
        for issue in issues:
            name = (issue.target or "").split(":", 1)[-1].strip()
            if name in _REVISABLE_SETTINGS_KEYS:
                block_names.add(name)
        if not block_names:
            return settings_data
        try:
            issue_lines = [
                f"- [{i.severity}] {i.target}：{i.problem}\n  修订方向：{i.fix_hint}" for i in issues
            ]
            strengths = "\n".join(f"- {s}" for s in report.strengths if s)
            prompt_parts = [
                "你是商业网文总编。审稿发现下列设定块存在问题，请**只重写这些块**，其余设定不动。",
                "【当前蓝图设定（完整，供理解上下文）】\n"
                + json.dumps(
                    {k: settings_data.get(k) for k in _REVISABLE_SETTINGS_KEYS if k in settings_data},
                    ensure_ascii=False, indent=1,
                ),
                "【审稿问题（必须逐条修掉）】\n" + "\n".join(issue_lines),
            ]
            if strengths:
                prompt_parts.append("【必须保留的亮点（修订不得破坏）】\n" + strengths)
            if exclusions.strip():
                prompt_parts.append("【创作禁区（不得触碰）】\n" + exclusions.strip())
            prompt_parts.append(
                "【输出要求】只输出一个 JSON 对象：{\"revised_blocks\": {<块名>: <重写后的完整块值>}}，"
                f"块名限于：{', '.join(sorted(block_names))}。每个块的结构必须与原块一致（同字段名、同类型）。"
                "不要输出任何解释。"
            )
            raw = await self.llm_service.get_llm_response(
                system_prompt="你是严格输出 JSON 的商业网文总编。",
                conversation_history=[{"role": "user", "content": "\n\n".join(prompt_parts)}],
                temperature=0.5,
                user_id=user_id,
                timeout=600.0,
                max_retries=1,
                max_tokens=_REVISION_MAX_TOKENS,
                reasoning_effort="low",
            )
            parsed = parse_llm_json(remove_think_tags(raw), default=None)
            revised_blocks = (parsed or {}).get("revised_blocks") if isinstance(parsed, dict) else None
            if not isinstance(revised_blocks, dict):
                return settings_data
            merged = dict(settings_data)
            applied: List[str] = []
            for name, value in revised_blocks.items():
                if name not in block_names or value is None:
                    continue
                original = settings_data.get(name)
                # 类型守卫：结构性块（dict/list）不允许被改成标量，防止修订产物污染蓝图
                if isinstance(original, dict) and not isinstance(value, dict):
                    continue
                if isinstance(original, list) and not isinstance(value, list):
                    continue
                merged[name] = value
                applied.append(name)
            if applied:
                logger.info("蓝图定向修订：重写设定块 %s", applied)
            return merged
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("蓝图设定块定向修订失败（保留原设定）: %s", exc)
            return settings_data

    # ------------------------------------------------------------------
    # 定向修订：章号区间
    # ------------------------------------------------------------------
    async def revise_chapter_ranges(
        self,
        *,
        outline_items: List[Dict[str, Any]],
        report: BlueprintReviewReport,
        settings_summary: str,
        outline_system_prompt: str,
        user_id: int,
        extract_items,
    ) -> List[Dict[str, Any]]:
        """只重写被点名章号区间的章纲，按章号合并回原章纲；失败返回原章纲。

        extract_items: 章纲解析函数（复用 blueprint_generation_service._extract_outline_items，
        保证修订产物过同一套清洗与规划字段提取）。
        """
        issues = report.issues_for_chapters()
        target_numbers: Set[int] = set()
        issue_lines: List[str] = []
        for issue in issues:
            span = parse_chapter_range(issue.target or "")
            if span is None:
                continue
            lo, hi = span
            if hi - lo > 60:  # 防御：点名整本书不算「定向」
                continue
            target_numbers.update(range(lo, hi + 1))
            issue_lines.append(
                f"- [{issue.severity}] 第{lo}-{hi}章：{issue.problem}\n  修订方向：{issue.fix_hint}"
            )
        existing_numbers = {item["chapter_number"] for item in outline_items}
        target_numbers &= existing_numbers
        if not target_numbers or not issue_lines:
            return outline_items
        try:
            current_lines = _outline_lines(
                [i for i in outline_items if i["chapter_number"] in target_numbers]
            )
            # 相邻上下文：目标区间前后各 2 章，保证修订后自然衔接
            context_numbers: Set[int] = set()
            for number in target_numbers:
                context_numbers.update(range(number - 2, number + 3))
            context_lines = _outline_lines(
                [
                    i for i in outline_items
                    if i["chapter_number"] in (context_numbers - target_numbers)
                ]
            )
            numbers_text = "、".join(str(n) for n in sorted(target_numbers))
            prompt = "\n\n".join(
                part for part in [
                    settings_summary,
                    f"【相邻章纲（不可改动，修订后须与其自然衔接）】\n{context_lines}" if context_lines else "",
                    f"【待修订章纲（当前版本）】\n{current_lines}",
                    "【审稿问题（必须逐条修掉）】\n" + "\n".join(issue_lines),
                    "【修订任务（最高优先级，覆盖上文生成任务）】\n"
                    f"只重写以下章号的章纲：第 {numbers_text} 章。"
                    "输出 JSON 对象 {\"chapter_outline\": [...]}，仅包含这些章号，"
                    "每章字段与原章纲格式一致（含章级规划字段）。"
                    "修订必须实质解决审稿问题（补爽点/加钩子/改节奏），不许只换措辞。",
                ] if part
            )
            raw = await self.llm_service.get_llm_response(
                system_prompt=outline_system_prompt,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.6,
                user_id=user_id,
                timeout=600.0,
                max_retries=1,
                max_tokens=_REVISION_MAX_TOKENS,
                reasoning_effort="low",
            )
            parsed = parse_llm_json(remove_think_tags(raw), default=None)
            revised_items = extract_items(parsed)
            revised_map = {
                item["chapter_number"]: item
                for item in revised_items
                if item["chapter_number"] in target_numbers
            }
            if not revised_map:
                return outline_items
            merged = [
                revised_map.get(item["chapter_number"], item) for item in outline_items
            ]
            logger.info("蓝图定向修订：重写章纲 %d 章（点名 %d 章）", len(revised_map), len(target_numbers))
            return merged
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("蓝图章纲定向修订失败（保留原章纲）: %s", exc)
            return outline_items

    # ------------------------------------------------------------------
    # 滚动章纲轻量审稿（写作台续排路径，旗舰档）
    # ------------------------------------------------------------------
    async def review_outline_range(
        self,
        *,
        settings_digest: str,
        new_items: List[Dict[str, Any]],
        foreshadowing_ledger: str,
        volume_replan: str,
        user_id: int,
    ) -> Optional[BlueprintReviewReport]:
        """只审新排章节的轻量审稿：一次 LLM 调用，失败返回 None。"""
        if not new_items:
            return None
        try:
            system_prompt = await self.prompt_service.get_prompt("blueprint_review")
            if not system_prompt:
                return None
            parts = [
                "【说明】本次为**滚动续排章纲的轻量审稿**：只审下方「新排章纲」这一段的节奏质量"
                "（开局强度与卷结构两维按不适用处理，给 0 分即可，不计问题）。",
                f"【蓝图设定摘要】\n{settings_digest}",
            ]
            if foreshadowing_ledger.strip():
                parts.append(f"【伏笔账本快照（未回收的伏笔，续排章纲应逐步推进/兑现）】\n{foreshadowing_ledger}")
            if volume_replan.strip():
                parts.append(f"【卷级重规划（当前生效的方向修订，新章纲必须服从）】\n{volume_replan}")
            parts.append("【新排章纲】\n" + _outline_lines(new_items))
            report = await self.llm_service.generate_structured(
                prompt="\n\n".join(parts),
                schema=BlueprintReviewReport,
                system_prompt=system_prompt,
                temperature=0.3,
                user_id=user_id,
                max_tokens=_REVIEW_MAX_TOKENS,
                default=None,
            )
            logger.info(
                "滚动章纲轻量审稿完成：total=%d issues=%d chapters=%d",
                report.total_score, len(report.issues), len(new_items),
            )
            return report
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("滚动章纲轻量审稿失败（跳过）: %s", exc)
            return None
