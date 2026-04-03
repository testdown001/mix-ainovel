# AIMETA P=力量体系工具|R=验证力量体系约束|NR=包装PowerSystemService|E=PowerSystemTool|X=internal|A=工具实现|D=asyncio
"""Power system constraints tool wrapping PowerSystemService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class PowerSystemTool(AgentTool):
    definition = ToolDefinition(
        name="power_system",
        description=(
            "Query the novel's power/magic systems and their level constraints. "
            "Returns system definitions, level abilities, limitations, and breakthrough conditions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "system_id": {
                    "type": "integer",
                    "description": "Specific power system ID to query (optional).",
                },
            },
            "required": [],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.power_system_service import PowerSystemService

        try:
            svc = PowerSystemService(context.session)
            system_id = args.get("system_id")

            if system_id:
                system = await svc.get_power_system(system_id)
                if not system:
                    return ToolResult(success=True, data={"found": False})
                return ToolResult(
                    success=True,
                    data={
                        "found": True,
                        "name": getattr(system, "name", ""),
                        "description": getattr(system, "description", ""),
                        "levels": [
                            {
                                "name": getattr(lv, "name", ""),
                                "rank": getattr(lv, "rank", 0),
                                "abilities": getattr(lv, "abilities", ""),
                                "limitations": getattr(lv, "limitations", ""),
                                "breakthrough_conditions": getattr(lv, "breakthrough_conditions", ""),
                            }
                            for lv in getattr(system, "levels", [])
                        ],
                    },
                )

            systems = await svc.get_power_systems_by_project(context.project_id)
            data = []
            for s in systems:
                data.append({
                    "id": getattr(s, "id", None),
                    "name": getattr(s, "name", ""),
                    "description": getattr(s, "description", ""),
                    "level_count": len(getattr(s, "levels", [])),
                })
            return ToolResult(success=True, data={"systems": data, "count": len(data)})

        except Exception as e:
            logger.error("PowerSystemTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))
