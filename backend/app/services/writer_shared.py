"""写作流程共享工具函数。

从 writer.py 和 pipeline_orchestrator.py 中提取的公共逻辑，
避免两处维护同一段代码。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

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
    if pattern_constraint:
        plan_input += f"\n{pattern_constraint}\n"

    try:
        response = await llm_service.get_llm_response(
            system_prompt=plan_prompt,
            conversation_history=[{"role": "user", "content": plan_input}],
            temperature=temperature,
            user_id=user_id,
            timeout=120.0,
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
        return mission
    except Exception as exc:
        logger.warning("生成章节导演脚本失败，将使用默认模式: %s", exc)
        return None


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
