# AIMETA P=实体注册工具|R=反幻觉实体查询|NR=包装EntityRegistryService|E=EntityRegistryTool|X=internal|A=工具实现|D=asyncio
"""Entity registry tool wrapping EntityRegistryService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class EntityRegistryTool(AgentTool):
    definition = ToolDefinition(
        name="entity_registry",
        description=(
            "Query the project's entity registry for canonical character/place/item names, "
            "resolve aliases, and detect unregistered names in text to prevent hallucination."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_all", "resolve_alias", "detect_unregistered", "build_alias_map"],
                    "description": "Action to perform.",
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["character", "location", "item", "organization"],
                    "description": "Filter by entity type (for get_all).",
                },
                "name": {
                    "type": "string",
                    "description": "Name to resolve (for resolve_alias).",
                },
                "text": {
                    "type": "string",
                    "description": "Text to scan for unregistered names (for detect_unregistered).",
                },
            },
            "required": ["action"],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.entity_registry_service import EntityRegistryService

        try:
            svc = EntityRegistryService(context.session)
            action = args["action"]

            if action == "get_all":
                entity_type = args.get("entity_type")
                entities = await svc.get_all_entities(
                    context.project_id, entity_type=entity_type,
                )
                data = []
                for e in entities:
                    data.append({
                        "id": getattr(e, "id", None),
                        "canonical_name": getattr(e, "canonical_name", str(e)),
                        "entity_type": getattr(e, "entity_type", ""),
                        "description": getattr(e, "description", ""),
                    })
                return ToolResult(success=True, data={"entities": data, "count": len(data)})

            if action == "resolve_alias":
                name = args.get("name")
                if not name:
                    return ToolResult(success=False, error="name required for resolve_alias")
                canonical = await svc.resolve_alias(context.project_id, name)
                return ToolResult(
                    success=True,
                    data={"input": name, "canonical_name": canonical, "resolved": canonical is not None},
                )

            if action == "detect_unregistered":
                text = args.get("text")
                if not text:
                    return ToolResult(success=False, error="text required for detect_unregistered")
                unregistered = await svc.detect_unregistered_names(context.project_id, text)
                return ToolResult(
                    success=True,
                    data={"unregistered": unregistered, "count": len(unregistered)},
                )

            if action == "build_alias_map":
                alias_map = await svc.build_alias_map(context.project_id)
                return ToolResult(success=True, data={"alias_map": alias_map})

            return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("EntityRegistryTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))
