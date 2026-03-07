# AIMETA P=户部Agent|R=技能系统|NR=管理和执行技能|E=HubuAgent|X=internal|A=Agent实现|D=asyncio
"""户部 Agent - 技能系统"""
from __future__ import annotations

from typing import Any, Dict

from .base import BaseAgent
from .message import AgentCapability, AgentContext, AgentMessageType, AgentResult


class HubuAgent(BaseAgent):
    """
    户部 Agent - 技能系统

    职责：
    1. 管理技能注册
    2. 执行技能处理
    3. 提供技能上下文
    """

    AGENT_NAME = "hubu"

    def _register_capabilities(self) -> None:
        """注册能力"""
        from .message import AgentCapability

        self._capabilities = {
            "apply_skill": AgentCapability(
                name="apply_skill",
                description="应用技能到内容",
                input_schema={"skill_id": "string", "content": "string"},
                output_schema={"result": "string"},
            ),
            "list_skills": AgentCapability(
                name="list_skills",
                description="列出所有可用技能",
                input_schema={},
                output_schema={"skills": "array"},
            ),
        }

    async def process(self, context: AgentContext) -> AgentResult:
        action = context.metadata.get("action", "list_skills")

        if action == "apply_skill":
            return await self._apply_skill(context)
        elif action == "list_skills":
            return await self._list_skills(context)
        elif action == "get_skill_context":
            return await self._get_skill_context(context)
        else:
            return AgentResult(
                status="failed",
                error=f"Unknown action: {action}"
            )

    async def _apply_skill(self, context: AgentContext) -> AgentResult:
        """应用技能"""
        skill_id = context.metadata.get("skill_id")
        content = context.metadata.get("content")
        params = context.metadata.get("params", {})

        try:
            from ..services.skill_service import SkillService

            skill_service = SkillService(self.session)
            result = await skill_service.apply_skill(
                skill_id=skill_id,
                content=content,
                params=params,
            )

            return AgentResult(
                status="completed",
                output={"result": result}
            )
        except Exception as e:
            return AgentResult(
                status="failed",
                error=str(e)
            )

    async def _list_skills(self, context: AgentContext) -> AgentResult:
        """列出技能"""
        try:
            from ..services.skill_service import SkillService

            skill_service = SkillService(self.session)
            skills = await skill_service.list_skills()

            return AgentResult(
                status="completed",
                output={"skills": skills}
            )
        except Exception as e:
            return AgentResult(
                status="failed",
                error=str(e)
            )

    async def _get_skill_context(self, context: AgentContext) -> AgentResult:
        """获取技能上下文"""
        return AgentResult(
            status="completed",
            output={"available_skills": list(self._capabilities.keys())}
        )
