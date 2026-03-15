# AIMETA P=伏笔技能|R=伏笔埋设与回收|NR=|E=ForeshadowingSkill|X=internal|A=技能|D=py|S=compute
"""
伏笔管理技能

处理伏笔埋设与回收，增强故事连贯性。
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

FORESHADOWING_SYSTEM = """你是一位伏笔管理专家。你的工作是：
- 在当前章节中埋设伏笔
- 识别可以回收的伏笔
- 确保伏笔与情节逻辑一致"""


class ForeshadowingSkill(SkillBase):
    """伏笔管理技能。"""

    def __init__(self, definition: SkillDefinition, llm_service: LLMService):
        super().__init__(definition)
        self.llm_service = llm_service

    async def execute(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """执行伏笔管理。"""
        params = params or {}
        mode = params.get("mode", "embed")  # embed | recall
        temp_map = {
            "subtle": 0.4,
            "moderate": 0.5,
            "strong": 0.6
        }
        temperature = temp_map.get(params.get("intensity", "moderate"), 0.5)

        prompt = self._build_prompt(context, mode)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=FORESHADOWING_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=context.metadata.get("user_id", 0),
                timeout=120.0,
                response_format=None,
            )

            result_content = response.strip() if response else context.content

            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "伏笔管理",
                original_content=context.content,
                transformed_content=result_content,
                success=True,
                metadata={"mode": mode}
            )

        except Exception as e:
            logger.error(f"Foreshadowing skill failed: {e}")
            return SkillResult(
                skill_id=self.id,
                capability_name=capability_name or "伏笔管理",
                original_content=context.content,
                transformed_content=context.content,
                success=False,
                error=str(e)
            )

    def _build_prompt(self, context: SkillContext, mode: str) -> str:
        """构建提示词。"""
        if mode == "embed":
            return f"""请在以下章节中适当埋设伏笔。

要求：
- 伏笔应该自然融入情节
- 为后续章节留出悬念
- 不要过于明显

原文：
{context.content}

直接输出调整后的文字。"""
        return f"""请在以下章节中回收之前埋设的伏笔。

原文：
{context.content}

直接输出调整后的文字。"""

    async def build_retrieval_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        mode = str((params or {}).get("mode") or "embed")
        hints = ["未回收伏笔列表", "相关章节片段", "前文章节摘要"]
        if mode == "recall":
            hints.append("优先检索已到期伏笔")
        else:
            hints.append("优先检索可延展的暗线")
        return hints

    async def build_prompt_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        mode = str((params or {}).get("mode") or "embed")
        if mode == "recall":
            return ["本章优先回收旧伏笔", "回收动作必须自然嵌入情节"]
        return ["本章适合埋设轻伏笔", "伏笔不能喧宾夺主"]

    async def build_verify_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> list[str]:
        mode = str((params or {}).get("mode") or "embed")
        if mode == "recall":
            return ["伏笔回收是否完成", "回收是否造成信息跳跃"]
        return ["伏笔埋设是否自然", "新伏笔是否具备后续可回收性"]
