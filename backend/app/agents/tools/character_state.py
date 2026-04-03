# AIMETA P=角色状态工具|R=查询/更新角色状态|NR=包装MemoryLayerService|E=CharacterStateTool|X=internal|A=工具实现|D=asyncio
"""Character state tool wrapping MemoryLayerService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class CharacterStateTool(AgentTool):
    definition = ToolDefinition(
        name="character_state",
        description=(
            "Query or update character states. Can retrieve current state of a character "
            "(emotions, relationships, location, abilities) or build a comprehensive chapter "
            "state context string for prompt injection."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_state", "get_all_states", "build_context", "get_memory_context"],
                    "description": "Action to perform.",
                },
                "character_name": {
                    "type": "string",
                    "description": "Character name (required for get_state).",
                },
                "involved_characters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of character names for context building.",
                },
            },
            "required": ["action"],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.memory_layer_service import MemoryLayerService

        try:
            svc = MemoryLayerService(context.session)
            action = args["action"]
            chapter = context.chapter_number or 1

            if action == "get_state":
                name = args.get("character_name")
                if not name:
                    return ToolResult(success=False, error="character_name required for get_state")
                state = await svc.get_character_state(context.project_id, name, chapter)
                if state is None:
                    return ToolResult(success=True, data={"found": False, "character": name})
                return ToolResult(
                    success=True,
                    data={
                        "found": True,
                        "character": name,
                        "state": {
                            k: v for k, v in vars(state).items()
                            if not k.startswith("_") and k != "metadata"
                        },
                    },
                )

            if action == "get_all_states":
                states = await svc.get_all_character_states(context.project_id, chapter)
                return ToolResult(
                    success=True,
                    data={
                        "count": len(states),
                        "characters": [
                            getattr(s, "character_name", str(s)) for s in states
                        ],
                    },
                )

            if action == "build_context":
                involved = args.get("involved_characters")
                ctx_text = await svc.build_chapter_state_context(
                    context.project_id, chapter, involved_characters=involved,
                )
                return ToolResult(success=True, data={"context": ctx_text or ""})

            if action == "get_memory_context":
                involved = args.get("involved_characters")
                ctx_text = await svc.get_memory_context(
                    context.project_id, chapter, involved_characters=involved,
                )
                return ToolResult(success=True, data={"context": ctx_text or ""})

            return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("CharacterStateTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))
