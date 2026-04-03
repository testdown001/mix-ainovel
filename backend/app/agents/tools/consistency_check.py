# AIMETA P=一致性检查工具|R=角色/时间线一致性|NR=包装ConsistencyService|E=ConsistencyCheckTool|X=internal|A=工具实现|D=asyncio
"""Consistency check tool wrapping ConsistencyService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class ConsistencyCheckTool(AgentTool):
    definition = ToolDefinition(
        name="consistency_check",
        description=(
            "Check chapter text for consistency violations against character states, "
            "timeline, worldview, and foreshadowing. Returns a list of violations with severity."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_text": {
                    "type": "string",
                    "description": "The chapter text to check for consistency.",
                },
                "include_foreshadowing": {
                    "type": "boolean",
                    "description": "Include foreshadowing consistency checks (default: true).",
                },
                "auto_fix": {
                    "type": "boolean",
                    "description": "Attempt to auto-fix critical violations (default: false).",
                },
            },
            "required": ["chapter_text"],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.consistency_service import ConsistencyService
        from ...services.llm_service import LLMService

        try:
            llm_service = LLMService(context.session)
            svc = ConsistencyService(context.session, llm_service)

            chapter_text = args["chapter_text"]
            include_foreshadowing = args.get("include_foreshadowing", True)
            auto_fix = args.get("auto_fix", False)

            if auto_fix:
                result = await svc.check_and_fix(
                    project_id=context.project_id,
                    chapter_text=chapter_text,
                    user_id=context.user_id,
                )
                return ToolResult(
                    success=True,
                    data=result,
                )

            check_result = await svc.check_consistency(
                project_id=context.project_id,
                chapter_text=chapter_text,
                user_id=context.user_id,
                include_foreshadowing=include_foreshadowing,
            )

            violations = []
            for v in getattr(check_result, "violations", []):
                violations.append({
                    "type": getattr(v, "violation_type", "unknown"),
                    "severity": str(getattr(v, "severity", "low")),
                    "description": getattr(v, "description", ""),
                    "suggestion": getattr(v, "suggestion", ""),
                })

            return ToolResult(
                success=True,
                data={
                    "is_consistent": getattr(check_result, "is_consistent", True),
                    "violation_count": len(violations),
                    "violations": violations,
                    "overall_score": getattr(check_result, "overall_score", 1.0),
                },
            )
        except Exception as e:
            logger.error("ConsistencyCheckTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))
