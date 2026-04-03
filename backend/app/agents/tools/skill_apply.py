# AIMETA P=技能应用工具|R=应用写作技能|NR=包装SkillService|E=SkillApplyTool|X=internal|A=工具实现|D=asyncio
"""Skill application tool wrapping SkillService."""
from __future__ import annotations

import logging
from types import SimpleNamespace

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class SkillApplyTool(AgentTool):
    definition = ToolDefinition(
        name="skill_apply",
        description=(
            "Apply writing skills (e.g., platinum-style prose, dialogue polish, pacing control) "
            "to modify or enhance chapter content. Can also list available skills or build "
            "skill policy directives for prompt injection."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_skills", "build_policy", "execute"],
                    "description": "Action: list_skills, build_policy, or execute.",
                },
                "skill_id": {
                    "type": "string",
                    "description": "Skill ID to apply (required for build_policy/execute).",
                },
                "capability_name": {
                    "type": "string",
                    "description": "Specific capability within the skill (optional).",
                },
                "params": {
                    "type": "object",
                    "description": "Extra parameters for skill execution.",
                },
            },
            "required": ["action"],
        },
        is_read_only=False,
        is_concurrency_safe=False,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.llm_service import LLMService
        from ...services.skill_service import SkillService

        try:
            llm_service = LLMService(context.session)
            svc = SkillService(llm_service)
            await svc.initialize()

            action = args["action"]

            if action == "list_skills":
                skills = await svc.list_skills()
                return ToolResult(
                    success=True,
                    data={
                        "skills": [
                            {"id": s.id, "name": s.name, "description": s.description}
                            for s in skills
                        ],
                    },
                )

            skill_id = args.get("skill_id")
            if not skill_id:
                return ToolResult(success=False, error="skill_id required for build_policy/execute")

            capability = args.get("capability_name")
            params = args.get("params")

            if action == "build_policy":
                skill_context = SimpleNamespace(
                    project_id=context.project_id,
                    chapter_number=context.chapter_number,
                    config=context.config,
                )
                policy = await svc.build_skill_policy(
                    skill_id, skill_context,
                    capability_name=capability, params=params,
                )
                return ToolResult(success=True, data={"policy": policy})

            if action == "execute":
                skill_context = SimpleNamespace(
                    project_id=context.project_id,
                    chapter_number=context.chapter_number,
                    config=context.config,
                )
                result = await svc.execute_skill(
                    skill_id, skill_context,
                    capability_name=capability, params=params,
                )
                return ToolResult(success=True, data={"result": result})

            return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("SkillApplyTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))
