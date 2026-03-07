# AIMETA P=白金作家文风技能|R=文风转换_专业作家风格|NR=|E=PlatinumStyleSkill|X=internal|A=技能|D=py|S=compute
"""
白金作家文风技能

将普通文字转换为专业小说家的写作风格。
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

PLATINUM_STYLE_SYSTEM = """你是一位白金级小说作家。你的文字应该：
- 老练、精准、有画面感
- 句子长短错落，有节奏感
- 描写细腻但不冗余
- 情绪内敛但有张力
- 让读者身临其境"""


class PlatinumStyleSkill(SkillBase):
    """白金作家文风技能。"""

    def __init__(self, definition: SkillDefinition, llm_service: LLMService):
        super().__init__(definition)
        self.llm_service = llm_service

    async def execute(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """执行白金文风转换。"""
        params = params or {}
        intensity = params.get("intensity", "moderate")
        preserve_original = params.get("preserve_original", True)

        # 根据强度调整 temperature
        temp_map = {
            "0.4,
subtle":             "moderate": 0.5,
            "strong": 0.6
        }
        temperature = temp_map.get(intensity, 0.5)

        # 构建提示词
        prompt = self._build_prompt(context, intensity)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=PLATINUM_STYLE_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=context.metadata.get("user_id", 0),
                timeout=120.0,
                response_format=None,
            )

            result_content = response.strip() if response else context.content

            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "白金文风",
                original_content=context.content,
                transformed_content=result_content,
                success=True,
                metadata={
                    "intensity": intensity,
                    "preserve_original": preserve_original,
                    "temperature": temperature
                }
            )

        except Exception as e:
            logger.error(f"Platinum style skill failed: {e}")
            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "白金文风",
                original_content=context.content,
                transformed_content=context.content if preserve_original else "",
                success=False,
                error=str(e)
            )

    def _build_prompt(self, context: SkillContext, intensity: str) -> str:
        """构建提示词。"""
        intensity_instruction = {
            "subtle": "轻微调整，保持原文 90% 以上的风格",
            "moderate": "中等调整，让文字更有质感但仍保持原貌",
            "strong": "大幅调整，彻底转变为专业作家风格"
        }

        instruction = intensity_instruction.get(intensity, intensity_instruction["moderate"])

        return f"""请将以下文字用白金作家风格重写。

要求：{instruction}

原文：
{context.content}

直接输出重写后的文字，不要任何说明。"""
