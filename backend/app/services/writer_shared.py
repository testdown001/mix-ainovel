"""写作流程共享工具函数。

从 writer.py 和 pipeline_orchestrator.py 中提取的公共逻辑，
避免两处维护同一段代码。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.json_utils import remove_think_tags, repair_json, unwrap_markdown_json

logger = logging.getLogger(__name__)


def extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


def extract_outline_planning_metadata(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从大纲生成的单章条目里挑出结构化规划字段，供落库到 `outline.metadata["planning"]`。

    `prompts/outline_generation.md` 每章都要求 LLM 产出 `narrative_phase` /
    `foreshadowing.plant|payoff` / `emotion_hook`，而落库只取 title+summary
    ——这三个字段章章生成、章章丢弃，等于每章都白付一笔 token。

    统一收在 `planning` 子键下，避免与 `prediction`（writer.py 写）、
    `revision_hint`（OutlineRevisionService 写）、导演脚本等既有键相撞。
    全部字段缺失时返回 None，调用方就不必写空壳。
    """
    planning: Dict[str, Any] = {}

    phase = item.get("narrative_phase")
    if isinstance(phase, str) and phase.strip():
        planning["narrative_phase"] = phase.strip()

    hook = item.get("emotion_hook")
    if isinstance(hook, str) and hook.strip():
        planning["emotion_hook"] = hook.strip()

    raw_fs = item.get("foreshadowing")
    if isinstance(raw_fs, dict):
        foreshadowing: Dict[str, List[str]] = {}
        for key in ("plant", "payoff"):
            value = raw_fs.get(key)
            # LLM 偶尔把单条伏笔写成字符串而非数组，一并归一
            if isinstance(value, str):
                value = [value] if value.strip() else []
            if isinstance(value, list):
                cleaned = [str(v).strip() for v in value if str(v).strip()]
                if cleaned:
                    foreshadowing[key] = cleaned
        if foreshadowing:
            planning["foreshadowing"] = foreshadowing

    # 章级规划五字段（chapter_function/hook_type/coolpoint/foreshadowing_ops/
    # must_not_include）：与蓝图 Stage B 同一套提取，落进同一个 planning 子键——
    # update_or_create_outline 见到 planning 会同步 upsert chapter_blueprints
    try:
        from .chapter_planning_service import extract_planning_from_item

        chapter_planning = extract_planning_from_item(item)
        if chapter_planning:
            planning.update(chapter_planning)
    except Exception:  # noqa: BLE001 - 规划提取失败不影响既有三字段
        pass

    return planning or None


def normalize_blueprint_relationships(blueprint_dict: Dict[str, Any]) -> Dict[str, Any]:
    """修正蓝图关系字段名：character_from -> from, character_to -> to。

    就地修改并返回 *blueprint_dict* 本身，方便链式调用。
    """
    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")
    return blueprint_dict


def build_blueprint_constraints_for_mission(
    *,
    blueprint_dict: Dict[str, Any],
    outline_title: str,
    outline_summary: str,
) -> str:
    """抽取蓝图硬约束，供章节导演脚本阶段参考。"""
    constraints: List[str] = []

    genre = blueprint_dict.get("genre")
    tone = blueprint_dict.get("tone")
    style = blueprint_dict.get("style")
    if genre:
        constraints.append(f"题材：{genre}")
    if tone:
        constraints.append(f"基调：{tone}")
    if style:
        constraints.append(f"文风：{style}")

    world_setting = blueprint_dict.get("world_setting")
    if isinstance(world_setting, dict):
        for key in ("summary", "core_rules", "power_system", "taboos", "factions", "conflicts"):
            if key not in world_setting:
                continue
            value = world_setting.get(key)
            if value is None:
                continue
            compact = value.strip() if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            if compact:
                constraints.append(f"{key}: {compact[:220]}")
            if len(constraints) >= 8:
                break

    character_names = [
        item.get("name")
        for item in (blueprint_dict.get("characters") or [])
        if isinstance(item, dict) and item.get("name")
    ]
    if character_names:
        constraints.append("角色锚点：" + "、".join(character_names[:10]))

    constraints.append(f"本章目标：{outline_title}｜{(outline_summary or '暂无摘要')[:180]}")
    return "\n".join(constraints)


async def generate_chapter_mission(
    llm_service,
    prompt_service,
    *,
    blueprint_dict: Dict[str, Any],
    previous_summary: str,
    previous_tail: str,
    outline_title: str,
    outline_summary: str,
    writing_notes: str,
    introduced_characters: List[str],
    all_characters: List[str],
    blueprint_constraints: str,
    user_id: int,
    temperature: float = 0.7,
    pattern_constraint: str = "",
) -> Optional[dict]:
    """
    L2 Director: 生成章节导演脚本（ChapterMission）。

    *temperature* 参数化：writer.py 调用时使用默认 0.7，
    pipeline_orchestrator.py 调用时传 0.3。
    """
    plan_prompt = await prompt_service.get_prompt("chapter_plan")
    if not plan_prompt:
        logger.warning("未配置 chapter_plan 提示词，跳过导演脚本生成")
        return None

    plan_input = f"""
[上一章摘要]
{previous_summary or "暂无（这是第一章）"}

[上一章结尾]
{previous_tail or "暂无（这是第一章）"}

[当前章节大纲]
标题：{outline_title}
摘要：{outline_summary}

[已登场角色]
{json.dumps(introduced_characters, ensure_ascii=False) if introduced_characters else "暂无"}

[全部角色]
{json.dumps(all_characters, ensure_ascii=False)}

[蓝图硬约束摘要]
{blueprint_constraints or "无"}

[写作指令]
{writing_notes or "无额外指令"}
"""
    # P4: 注入动态字数配置到导演脚本生成
    from ..core.config import settings
    from ..core.constants import CHAPTER_MIN_WORDS, CHAPTER_MAX_WORDS
    try:
        wc_min = int(getattr(settings, "writer_chapter_word_count_min", CHAPTER_MIN_WORDS))
        wc_max = int(getattr(settings, "writer_chapter_word_count_max", CHAPTER_MAX_WORDS))
    except (TypeError, ValueError):
        wc_min, wc_max = CHAPTER_MIN_WORDS, CHAPTER_MAX_WORDS
    plan_input += (
        f"\n[章节字数限制]\n"
        f"正文必须控制在 {wc_min}-{wc_max} 字之间。"
        f"输出JSON中 word_budget_total 必须设置在此范围内（推荐 {wc_min + (wc_max - wc_min) // 2}）。\n"
    )
    if pattern_constraint:
        plan_input += f"\n{pattern_constraint}\n"

    try:
        response = await llm_service.get_llm_response(
            system_prompt=plan_prompt,
            conversation_history=[{"role": "user", "content": plan_input}],
            temperature=temperature,
            user_id=user_id,
            timeout=60.0,
            max_retries=0,
            reasoning_effort="low",
        )
        cleaned = remove_think_tags(response)
        # thinking 模型可能将全部内容包裹在 <think> 标签内，
        # 清除后为空时回退到原始响应中提取 JSON
        if not cleaned:
            logger.info("remove_think_tags 后内容为空，回退到原始响应提取 JSON (len=%d)", len(response))
            cleaned = response
        normalized = unwrap_markdown_json(cleaned)
        if not normalized:
            logger.warning("unwrap_markdown_json 提取结果为空，原始响应前200字: %s", response[:200])
            return None
        try:
            mission = json.loads(normalized)
        except json.JSONDecodeError:
            repaired = repair_json(normalized)
            mission = json.loads(repaired)
        logger.info("成功生成章节导演脚本: macro_beat=%s", mission.get("macro_beat"))
        mission = await _review_and_maybe_fix_mission(
            llm_service, mission,
            plan_prompt=plan_prompt, plan_input=plan_input,
            outline_summary=outline_summary, previous_summary=previous_summary,
            temperature=temperature, user_id=user_id,
        )
        return mission
    except Exception as exc:
        logger.warning("生成章节导演脚本失败，将使用默认模式: %s", exc)
        return None


async def _review_and_maybe_fix_mission(
    llm_service,
    mission: dict,
    *,
    plan_prompt: str,
    plan_input: str,
    outline_summary: str,
    previous_summary: str,
    temperature: float,
    user_id: int,
) -> dict:
    """对导演脚本做一次轻量前置评审（评分通道，未配置则跳过，绝不阻断主流程）。

    评 3 项：宏观节拍是否推进主线 / 是否与前文冲突 / 章尾钩子是否有效。
    不达标则带反馈重生成一次；任何异常都原样返回原脚本。
    依据 CritiCS：评审施加于规划阶段比正文阶段收益更高。
    """
    try:
        grader_config = await llm_service._resolve_grader_llm_config()
    except Exception:
        grader_config = None
    if grader_config is None:
        return mission

    def _parse_verdict(raw: str) -> dict:
        cleaned = remove_think_tags(raw) or raw
        normalized = unwrap_markdown_json(cleaned)
        if not normalized:
            return {}
        try:
            return json.loads(normalized)
        except Exception:
            try:
                return json.loads(repair_json(normalized))
            except Exception:
                return {}

    review_system = "你是严格的网文章节规划审稿人。只输出 JSON，不要解释。"
    review_user = (
        "审查以下章节导演脚本，针对三项各给 true/false：\n"
        "1. advances_mainline：宏观节拍是否推进主线（而非原地打转/纯过渡）\n"
        "2. conflicts_prev：是否与[前文摘要]存在设定或情节冲突\n"
        "3. hook_effective：章尾钩子是否具体有效（而非空泛升华）\n\n"
        f"[前文摘要]\n{(previous_summary or '无')[:800]}\n\n"
        f"[本章大纲摘要]\n{(outline_summary or '无')[:500]}\n\n"
        f"[导演脚本]\n{json.dumps(mission, ensure_ascii=False)[:2500]}\n\n"
        "输出格式：{\"advances_mainline\":true,\"conflicts_prev\":false,\"hook_effective\":true,\"issues\":\"一句话\"}"
    )
    try:
        raw = await llm_service.get_grader_llm_response(
            system_prompt=review_system,
            conversation_history=[{"role": "user", "content": review_user}],
            temperature=0.1,
            timeout=20.0,
            max_tokens=500,
            max_retries=0,
            reasoning_effort="low",
        )
    except Exception as exc:
        logger.debug("mission 评审调用失败，跳过: %s", exc)
        return mission

    verdict = _parse_verdict(raw) if raw else {}
    if not isinstance(verdict, dict):
        return mission
    advances = verdict.get("advances_mainline", True)
    conflicts = verdict.get("conflicts_prev", False)
    hook_ok = verdict.get("hook_effective", True)
    if advances and (not conflicts) and hook_ok:
        return mission

    # 规划节奏/钩子不足不值得再付一次完整 Mission 生成；把意见留给正文提示词即可。
    # 只有与既有剧情发生明确冲突时，才允许一次纠错重生成。
    if not conflicts:
        warnings = mission.setdefault("planning_warnings", [])
        if not advances:
            warnings.append("本章必须产生明确的主线、关系或局势变化")
        if not hook_ok:
            warnings.append("章末必须落在 POV 可感知的具体动作、画面、声音或半句台词")
        return mission

    issues = str(verdict.get("issues", ""))[:300]
    logger.info("mission 前置评审未达标，带反馈重生成一次: %s", issues)
    fix_input = plan_input + (
        f"\n[上一版导演脚本被审稿驳回]\n{issues}\n"
        "请修正后重新输出完整 JSON 导演脚本（推进主线、消除与前文冲突、给出具体章尾钩子）。\n"
    )
    try:
        response = await llm_service.get_llm_response(
            system_prompt=plan_prompt,
            conversation_history=[{"role": "user", "content": fix_input}],
            temperature=temperature,
            user_id=user_id,
            timeout=60.0,
            max_retries=0,
            reasoning_effort="low",
        )
        cleaned = remove_think_tags(response) or response
        normalized = unwrap_markdown_json(cleaned)
        if normalized:
            try:
                fixed = json.loads(normalized)
            except Exception:
                fixed = json.loads(repair_json(normalized))
            if isinstance(fixed, dict) and fixed.get("macro_beat"):
                return fixed
    except Exception as exc:
        logger.debug("mission 重生成失败，沿用原脚本: %s", exc)
    return mission



async def rewrite_with_guardrails(
    llm_service,
    prompt_service,
    *,
    original_text: str,
    chapter_mission: Optional[dict],
    violations_text: str,
    user_id: int,
) -> str:
    """
    使用护栏修复提示词重写违规内容。

    空内容回退逻辑：remove_think_tags 后为空时回退到原始响应。
    """
    rewrite_prompt = await prompt_service.get_prompt("rewrite_guardrails")
    if not rewrite_prompt:
        logger.warning("未配置 rewrite_guardrails 提示词，跳过自动修复")
        return original_text

    rewrite_input = f"""
[原文]
{original_text}

[章节导演脚本]
{json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无"}

[违规列表]
{violations_text}
"""

    try:
        response = await llm_service.get_llm_response(
            system_prompt=rewrite_prompt,
            conversation_history=[{"role": "user", "content": rewrite_input}],
            temperature=0.3,
            user_id=user_id,
            timeout=300.0,
            response_format=None,
            max_tokens=int(len(original_text) * 1.2),
        )
        cleaned = remove_think_tags(response)
        if not cleaned or not cleaned.strip():
            logger.info("护栏修复: remove_think_tags 后为空，回退原始响应 (len=%d)", len(response))
            cleaned = response
        logger.info("成功修复违规内容")
        return cleaned
    except Exception as exc:
        logger.warning("自动修复失败，返回原文: %s", exc)
        return original_text


def create_vector_store_or_none():
    """安全创建 VectorStoreService，失败返回 None。"""
    from ..core.config import settings
    from .vector_store_service import VectorStoreService

    if not settings.vector_store_enabled:
        return None
    try:
        return VectorStoreService()
    except RuntimeError as exc:
        logger.warning("向量库初始化失败: %s", exc)
        return None


async def resolve_version_count(
    session: AsyncSession,
    requested_count: Optional[int] = None,
) -> int:
    """解析章节版本数量配置。

    优先级：
    1) requested_count（来自 API 请求）
    2) SystemConfig: writer.chapter_versions / writer.version_count
    3) ENV: WRITER_CHAPTER_VERSION_COUNT / WRITER_CHAPTER_VERSIONS / WRITER_VERSION_COUNT
    4) settings.writer_chapter_versions（默认=2）
    """
    from ..core.config import settings
    from ..repositories.system_config_repository import SystemConfigRepository

    if requested_count:
        try:
            count = int(requested_count)
            # 请求侧上限 5：versions 直接放大整条生成流水线的 LLM 成本，
            # 不能由客户端无界指定；管理员通道（SystemConfig/ENV）不受此限
            return max(1, min(count, 5))
        except (TypeError, ValueError):
            pass

    repo = SystemConfigRepository(session)
    for key in ("writer.chapter_versions", "writer.version_count"):
        record = await repo.get_by_key(key)
        if record and record.value:
            try:
                val = int(record.value)
                if val >= 1:
                    return val
            except ValueError:
                pass

    for env in ("WRITER_CHAPTER_VERSION_COUNT", "WRITER_CHAPTER_VERSIONS", "WRITER_VERSION_COUNT"):
        v = os.getenv(env)
        if v:
            try:
                val = int(v)
                if val >= 1:
                    return val
            except ValueError:
                pass

    return int(settings.writer_chapter_versions)

