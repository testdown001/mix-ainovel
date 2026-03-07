# AIMETA P=情绪增强技能|R=情感张力_情绪描写|NR=|E=EmotionBoostSkill|X=internal|A=技能|D=py|S=compute
"""
情绪增强技能

提升情感张力，让情绪表达更强烈。
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

EMOTION_BOOST_SYSTEM = """你是一位情感渲染专家。你的工作是：
- 增强情绪张力和感染力
- 让情感表达更加细腻动人
- 通过细节和感官描写传递情绪"""


class EmotionBoostSkill(SkillBase):
    """情绪增强技能。"""

    def __init__(self, definition: SkillDefinition, llm_service: LLMService):
        super().__init__(definition)
        self.llm_service = llm_service

    async def execute(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """执行情绪增强。"""
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
                system_prompt=EMOTION_BOOST_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=context.metadata.get("user_id", 0),
                timeout=120.0,
                response_format=None,
            )

            result_content = response.strip() if response else context.content

            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "情绪增强",
                original_content=context.content,
                transformed_content=result_content,
                success=True,
                metadata={
                    "intensity": intensity,
                    "preserve_original": preserve_original
                }
            )

        except Exception as e:
            logger.error(f"Emotion boost skill failed: {e}")
            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "情绪增强",
                original_content=context.content,
                transformed_content=context.content if preserve_original else "",
                success=False,
                error=str(e)
            )

    def _build_prompt(self, context: SkillContext, intensity: str) -> str:
        """构建提示词。"""
        intensity_instruction = {
            "subtle": "轻微增强情感表达，让原文更具感染力",
            "moderate": "中等增强，让情绪更加饱满动人",
            "strong": "大幅增强，让情感表达强烈冲击读者"
        }

        instruction = intensity_instruction.get(intensity, intensity_instruction["moderate"])
        chapter_type = context.chapter_info.get("type", "普通")

        return f"""请增强以下章节的情感表达。

要求：{instruction}
本章类型：{chapter_type}

原文：
{context.content}

直接输出调整后的文字，不要任何说明。"""
