# AIMETA P=伏笔线索工具|R=查询活跃伏笔|NR=包装ForeshadowingService|E=ForeshadowingTool|X=internal|A=工具实现|D=asyncio
"""Foreshadowing tool wrapping ForeshadowingService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class ForeshadowingTool(AgentTool):
    definition = ToolDefinition(
        name="foreshadowing",
        description=(
            "Query active and unresolved foreshadowing elements in the novel. "
            "Useful for checking which plot threads need to be continued or resolved."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_unresolved", "get_all", "get_reminders"],
                    "description": "Action: get_unresolved (default), get_all, or get_reminders.",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "resolved", "abandoned"],
                    "description": "Filter by status (only for get_all).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default: 50).",
                },
            },
            "required": [],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.foreshadowing_service import ForeshadowingService

        try:
            svc = ForeshadowingService(context.session)
            action = args.get("action", "get_unresolved")
            limit = args.get("limit", 50)

            if action == "get_unresolved":
                chapter = context.chapter_number or 1
                items = await svc.get_unresolved_foreshadowings(context.project_id, chapter)
                data = []
                for f in items[:limit]:
                    data.append({
                        "id": getattr(f, "id", None),
                        "description": getattr(f, "description", str(f)),
                        "planted_chapter": getattr(f, "planted_chapter", None),
                        "foreshadowing_type": getattr(f, "foreshadowing_type", None),
                    })
                return ToolResult(success=True, data={"unresolved": data, "count": len(data)})

            if action == "get_all":
                status = args.get("status")
                items, total = await svc.get_foreshadowings(
                    context.project_id, status=status, limit=limit,
                )
                data = []
                for f in items:
                    data.append({
                        "id": getattr(f, "id", None),
                        "description": getattr(f, "description", str(f)),
                        "status": getattr(f, "status", None),
                        "planted_chapter": getattr(f, "planted_chapter", None),
                    })
                return ToolResult(success=True, data={"items": data, "total": total})

            if action == "get_reminders":
                reminders = await svc.get_active_reminders(context.project_id, limit=limit)
                data = []
                for r in reminders:
                    data.append({
                        "id": getattr(r, "id", None),
                        "message": getattr(r, "message", str(r)),
                    })
                return ToolResult(success=True, data={"reminders": data, "count": len(data)})

            return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("ForeshadowingTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))
