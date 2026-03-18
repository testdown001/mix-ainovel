from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from ..core.config import settings
from ..utils.json_utils import remove_think_tags, repair_json, unwrap_markdown_json

logger = logging.getLogger(__name__)


class MissionBuilderService:
    """封装 fast/basic 路径下的章节 mission 构造。"""

    def __init__(self, prompt_service, llm_service, generation_policy_service):
        self.prompt_service = prompt_service
        self.llm_service = llm_service
        self.generation_policy_service = generation_policy_service

    async def build_lite_chapter_mission(
        self,
        *,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        previous_summary: str,
        previous_tail: str,
        chapter_blueprint,
        user_id: int,
    ) -> Optional[Dict[str, object]]:
        plan_lite_prompt = await self.prompt_service.get_prompt("chapter_plan_lite")
        if not plan_lite_prompt:
            logger.warning("未配置 chapter_plan_lite 提示词，回退到规则拼装")
            return None

        constraints = (
            dict(chapter_blueprint.mission_constraints or {})
            if chapter_blueprint and isinstance(chapter_blueprint.mission_constraints, dict)
            else {}
        )
        min_words, max_words, target_words = self.generation_policy_service.resolve_word_count_bounds()
        budget_cfg = constraints.get("word_budget") or {}
        word_target = int(budget_cfg.get("target") or target_words)

        plan_input = f"""
[上一章摘要]
{previous_summary or "暂无（这是第一章）"}

[上一章结尾]
{previous_tail or "暂无（这是第一章）"}

[当前章节大纲]
标题：{outline_title}
摘要：{outline_summary}

[写作指令]
{writing_notes or "无额外指令"}

[章节字数限制]
正文必须控制在 {min_words}-{max_words} 字之间。word_budget_total 推荐 {word_target}。
"""
        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=plan_lite_prompt,
                conversation_history=[{"role": "user", "content": plan_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=60.0,
                response_format=None,
                disable_thinking=not settings.writer_enable_thinking,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned or response)
            parsed = json.loads(repair_json(normalized))
            if not isinstance(parsed, dict):
                logger.warning("轻量导演脚本返回非对象，回退到规则拼装")
                return None

            fallback = self.build_fast_chapter_mission(
                chapter_number=chapter_number,
                outline_title=outline_title,
                outline_summary=outline_summary,
                writing_notes=writing_notes,
                chapter_blueprint=chapter_blueprint,
            )
            result = dict(fallback)
            result.update({key: value for key, value in parsed.items() if value is not None})

            raw_budget = result.get("word_budget")
            merged_budget = dict(fallback.get("word_budget") or {})
            if isinstance(raw_budget, dict):
                merged_budget.update({key: value for key, value in raw_budget.items() if value is not None})
            result["word_budget"] = merged_budget

            if not isinstance(result.get("satisfaction_design"), dict):
                sat_type = result.get("satisfaction_design") or fallback.get("satisfaction_design", {}).get("type") or "推进成长"
                result["satisfaction_design"] = {"type": sat_type}

            for key in ("scene_list", "allowed_new_characters", "must_include", "must_not_include"):
                value = result.get(key)
                if not isinstance(value, list):
                    result[key] = list(value) if isinstance(value, tuple) else []

            if not result.get("macro_beat_description"):
                result["macro_beat_description"] = fallback["macro_beat_description"]
            if not result.get("chapter_type"):
                result["chapter_type"] = fallback["chapter_type"]
            if not result.get("macro_beat"):
                result["macro_beat"] = fallback["macro_beat"]

            return result
        except Exception as exc:
            logger.warning("轻量导演脚本生成失败，回退到规则拼装: %s", exc)
            return None

    def build_fast_chapter_mission(
        self,
        *,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        chapter_blueprint,
    ) -> Dict[str, object]:
        constraints = (
            dict(chapter_blueprint.mission_constraints or {})
            if chapter_blueprint and isinstance(chapter_blueprint.mission_constraints, dict)
            else {}
        )
        min_words, max_words, target_words = self.generation_policy_service.resolve_word_count_bounds()
        budget_cfg = constraints.get("word_budget") or {}
        word_budget = {
            "min": int(budget_cfg.get("min") or min_words),
            "target": int(budget_cfg.get("target") or target_words),
            "max": int(budget_cfg.get("max") or max_words),
            "total": int(budget_cfg.get("target") or target_words),
        }
        if word_budget["max"] < word_budget["min"]:
            word_budget["max"] = word_budget["min"]

        chapter_function = (
            (chapter_blueprint.chapter_function if chapter_blueprint else None)
            or "progression"
        )
        satisfaction_type = {
            "climax": "高潮爆发",
            "turning": "转折兑现",
            "revelation": "信息揭示",
            "resolution": "阶段收束",
            "interlude": "无（蓄力中）",
            "buildup": "无（蓄力中）",
            "progression": "推进成长",
        }.get(chapter_function, "推进成长")

        focus = (
            (chapter_blueprint.chapter_focus if chapter_blueprint else None)
            or (chapter_blueprint.brief_summary if chapter_blueprint else None)
            or outline_summary
            or outline_title
        )
        must_include = constraints.get("must_include") or []
        must_not_include = constraints.get("must_not_include") or []
        scene_list = constraints.get("scene_list") or []
        allowed_new_characters = constraints.get("allowed_new_characters") or []
        pov_character = constraints.get("pov_character")

        notes_block = ""
        if writing_notes and writing_notes != "无额外写作指令":
            notes_block = f"；用户指令：{writing_notes}"
        mission_summary = f"第{chapter_number}章核心任务：{focus}{notes_block}"

        return {
            "chapter_type": chapter_function,
            "macro_beat": chapter_function,
            "macro_beat_description": mission_summary,
            "satisfaction_design": {"type": satisfaction_type},
            "word_budget": word_budget,
            "scene_list": scene_list,
            "allowed_new_characters": allowed_new_characters,
            "must_include": must_include,
            "must_not_include": must_not_include,
            "pov": pov_character,
        }
