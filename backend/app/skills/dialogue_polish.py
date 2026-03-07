# AIMETA P=对话润色技能|R=对话优化_角色性格|NR=|E=DialoguePolishSkill|X=internal|A=技能|D=py|S=compute
"""
对话润色技能

优化角色对话，使对白更贴合角色性格和场景。
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

DIALOGUE_POLISH_SYSTEM = """你是一位角色对话专家。你的工作是让角色的对白：
- 符合角色性格、身份、情绪状态
- 有个人特色（口头禅、说话方式）
- 推动情节发展
- 让读者感受到角色魅力"""


class DialoguePolishSkill(SkillBase):
    """对话润色技能。"""

    def __init__(self, definition: SkillDefinition, llm_service: LLMService):
        super().__init__(definition)
        self.llm_service = llm_service

    async def execute(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """执行对话润色。"""
        params = params or {}
        intensity = params.get("intensity", "moderate")
        preserve_original = params.get("preserve_original", True)

        temp_map = {
            "subtle": 0.4,
            "moderate": 0.5,
            "strong": 0.6
        }
        temperature = temp_map.get(intensity, 0.5)

        prompt = self._build_prompt(context, intensity)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=DIALOGUE_POLISH_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=context.metadata.get("user_id", 0),
                timeout=120.0,
                response_format=None,
            )

            result_content = response.strip() if response else context.content

            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "对话润色",
                original_content=context.content,
                transformed_content=result_content,
                success=True,
                metadata={
                    "intensity": intensity,
                    "preserve_original": preserve_original
                }
            )

        except Exception as e:
            logger.error(f"Dialogue polish skill failed: {e}")
            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "对话润色",
                original_content=context.content,
                transformed_content=context.content if preserve_original else "",
                success=False,
                error=str(e)
            )

    def _build_prompt(self, context: SkillContext, intensity: str) -> str:
        """构建提示词。"""
        # 获取角色信息
        characters = context.get_characters_in_scene()
        char_info = ""
        if characters:
            char_info = "\n角色设定：\n"
            for char in characters:
                char_info += f"- {char.get('name', '未知')}: {char.get('description', '无描述')}\n"

        intensity_instruction = {
            "subtle": "轻微润色，让对话更自然",
            "moderate": "中等润色，凸显角色特色",
            "strong": "大幅润色，重新设计对话风格"
        }

        instruction = intensity_instruction.get(intensity, intensity_instruction["moderate"])

        return f"""请润色以下小说对话。

要求：{instruction}
{char_info}
原文：
{context.content}

直接输出润色后的对话，不要任何说明。"""
