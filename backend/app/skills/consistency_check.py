# AIMETA P=一致性检查技能|R=前后一致_逻辑检查|NR=|E=ConsistencyCheckSkill|X=internal|A=技能|D=py|S=compute
"""
一致性检查技能

检查前后情节、人物设定的一致性。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..services.llm_service import LLMService
from .skill_base import (
    SkillBase,
    SkillDefinition,
    SkillContext,
    SkillResult,
)

logger = logging.getLogger(__name__)

CONSISTENCY_SYSTEM = """你是一位逻辑审查专家。你的工作是：
- 检查前后情节的一致性
- 检查人物行为与设定的符合度
- 检查世界观的统一性
- 指出不一致的地方"""


class ConsistencyCheckSkill(SkillBase):
    """一致性检查技能。"""

    def __init__(self, definition: SkillDefinition, llm_service: LLMService):
        super().__init__(definition)
        self.llm_service = llm_service

    async def execute(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """执行一致性检查。"""
        params = params or {}
        preserve_original = params.get("preserve_original", True)

        temp_map = {
            "subtle": 0.4,
            "moderate": 0.5,
            "strong": 0.6
        }
        temperature = temp_map.get(params.get("intensity", "moderate"), 0.5)

        prompt = self._build_prompt(context)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=CONSISTENCY_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=context.metadata.get("user_id", 0),
                timeout=120.0,
                response_format=None,
            )

            issues = self._parse_issues(response or "")

            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "一致性检查",
                original_content=context.content,
                transformed_content=context.content,
                success=True,
                metadata={
                    "issues": issues,
                    "preserve_original": preserve_original
                }
            )

        except Exception as e:
            logger.error(f"Consistency check skill failed: {e}")
            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "一致性检查",
                original_content=context.content,
                transformed_content=context.content,
                success=False,
                error=str(e)
            )

    def _build_prompt(self, context: SkillContext) -> str:
        """构建提示词。"""
        characters = context.character_profiles
        char_info = "\n".join([
            f"- {c.get('name', '未知')}: {c.get('description', '无')}"
            for c in characters
        ]) if characters else "无角色设定"

        previous = f"\n前章摘要：\n{context.previous_summary}" if context.previous_summary else ""

        return f"""请检查以下章节的一致性问题。

角色设定：
{char_info}
{previous}

原文：
{context.content}

请列出发现的一致性问题（如果有），包括：
1. 情节矛盾
2. 人物行为与设定不符
3. 世界观不一致

如果没有问题，请回复"未发现一致性问题"。"""

    def _parse_issues(self, response: str) -> list[str]:
        """解析 LLM 返回的问题列表。"""
        if "未发现一致性问题" in response or "没有" in response.lower():
            return []

        lines = response.split('\n')
        issues = [l.strip() for l in lines if l.strip() and not l.startswith('请') and not l.startswith('角色')]

        return issues
