# AIMETA P=节奏控制技能|R=叙事节奏_长短句|NR=|E=RhythmControlSkill|X=internal|A=技能|D=py|S=compute
"""
节奏控制技能

调整章节节奏，使叙事张弛有度。
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

RHYTHM_CONTROL_SYSTEM = """你是一位文字节奏师。你的工作是让文字的呼吸节奏恰到好处：
- 关键动作用短句砸（≤10字）
- 氛围铺陈用长句（30-50字）
- 紧张场景段落变短变密
- 松弛场景段落变长变舒展
- 整体有快有慢、有轻有重"""


class RhythmControlSkill(SkillBase):
    """节奏控制技能。"""

    def __init__(self, definition: SkillDefinition, llm_service: LLMService):
        super().__init__(definition)
        self.llm_service = llm_service

    async def execute(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """执行节奏控制。"""
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
                system_prompt=RHYTHM_CONTROL_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=context.metadata.get("user_id", 0),
                timeout=120.0,
                response_format=None,
            )

            result_content = response.strip() if response else context.content

            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "节奏控制",
                original_content=context.content,
                transformed_content=result_content,
                success=True,
                metadata={
                    "intensity": intensity,
                    "preserve_original": preserve_original
                }
            )

        except Exception as e:
            logger.error(f"Rhythm control skill failed: {e}")
            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "节奏控制",
                original_content=context.content,
                transformed_content=context.content if preserve_original else "",
                success=False,
                error=str(e)
            )

    def _build_prompt(self, context: SkillContext, intensity: str) -> str:
        """构建提示词。"""
        intensity_instruction = {
            "subtle": "轻微调整，保持原文 90% 以上的节奏",
            "moderate": "中等调整，让节奏更有起伏",
            "strong": "大幅调整，重新设计节奏层次"
        }

        instruction = intensity_instruction.get(intensity, intensity_instruction["moderate"])
        chapter_info = context.chapter_info.get("type", "普通")

        return f"""请调整以下章节的节奏。

要求：{instruction}
本章类型：{chapter_info}

原文：
{context.content}

直接输出调整后的文字，不要任何说明。"""

    async def build_retrieval_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        chapter_type = context.chapter_info.get("type", "普通章")
        return [
            "近5章节奏分布",
            "高潮密度",
            f"章节类型: {chapter_type}",
        ]

    async def build_prompt_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        intensity = str((params or {}).get("intensity") or self.definition.config.default)
        return [
            f"节奏控制强度: {intensity}",
            "关键动作使用短句推进",
            "铺陈段落保持呼吸感和层次变化",
        ]

    async def build_verify_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        return ["节奏目标达成度", "段落密度是否匹配章节类型"]
