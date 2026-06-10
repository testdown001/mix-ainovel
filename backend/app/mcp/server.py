# AIMETA P=MCP服务器|R=暴露写作工具给外部Agent|NR=支持stdio和HTTP传输|E=MCPServer|X=internal|A=协议服务|D=asyncio
"""
MCP (Model Context Protocol) server for Arboris-Novel.

Exposes key writing tools as MCP tools so external AI agents (Claude Code, Cursor, etc.)
can query novel state, trigger generation, and review content.

Usage:
  # stdio transport (for local agent integration):
  python -m backend.app.mcp.server --transport stdio

  # HTTP transport (for remote integration):
  python -m backend.app.mcp.server --transport http --port 8765
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "arboris-novel"
MCP_SERVER_VERSION = "0.1.0"

TOOL_MANIFEST = [
    {
        "name": "novel_rag_retrieve",
        "description": "Retrieve relevant context from the novel's knowledge base via vector similarity search.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Novel project ID."},
                "query_text": {"type": "string", "description": "Search query."},
                "top_k": {"type": "integer", "description": "Number of results (default: 5)."},
            },
            "required": ["project_id", "query_text"],
        },
    },
    {
        "name": "novel_generate_chapter",
        "description": "Generate a chapter of the novel using the writing pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Novel project ID."},
                "chapter_number": {"type": "integer", "description": "Chapter number to generate."},
                "writing_notes": {"type": "string", "description": "Optional writing instructions."},
                "preset": {"type": "string", "enum": ["fast", "standard", "premium"], "description": "Generation preset."},
            },
            "required": ["project_id", "chapter_number"],
        },
    },
    {
        "name": "novel_review_chapter",
        "description": "Review a chapter for quality, consistency, and other dimensions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Novel project ID."},
                "chapter_text": {"type": "string", "description": "Chapter content to review."},
                "chapter_number": {"type": "integer", "description": "Chapter number."},
            },
            "required": ["project_id", "chapter_text"],
        },
    },
    {
        "name": "novel_consistency_check",
        "description": "Check chapter text for consistency violations against established character states, timeline, and worldview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Novel project ID."},
                "chapter_text": {"type": "string", "description": "Chapter text to check."},
            },
            "required": ["project_id", "chapter_text"],
        },
    },
    {
        "name": "novel_get_character_states",
        "description": "Get current states of all characters in the novel project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Novel project ID."},
                "chapter_number": {"type": "integer", "description": "Chapter number for state context."},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "novel_get_foreshadowing",
        "description": "Get active and unresolved foreshadowing elements in the novel.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Novel project ID."},
                "chapter_number": {"type": "integer", "description": "Current chapter number."},
            },
            "required": ["project_id"],
        },
    },
]


class MCPServer:
    """Lightweight MCP-compatible server that delegates to Arboris-Novel agent tools."""

    def __init__(self) -> None:
        self._initialized = False

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "initialize":
            return self._ok(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
            })

        if method == "initialized":
            self._initialized = True
            return self._ok(req_id, None)

        if method == "tools/list":
            return self._ok(req_id, {"tools": TOOL_MANIFEST})

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = await self._dispatch_tool(tool_name, arguments)
            return self._ok(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
                "isError": not result.get("success", True),
            })

        return self._error(req_id, -32601, f"Method not found: {method}")

    async def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Route MCP tool calls to the internal agent tool system."""
        from ..agents.tools import create_default_registry
        from ..agents.tools.base import AgentToolContext

        tool_name_map = {
            "novel_rag_retrieve": "rag_retrieve",
            "novel_generate_chapter": "generate",
            "novel_review_chapter": "review",
            "novel_consistency_check": "consistency_check",
            "novel_get_character_states": "character_state",
            "novel_get_foreshadowing": "foreshadowing",
        }

        internal_name = tool_name_map.get(name)
        if not internal_name:
            return {"success": False, "error": f"Unknown tool: {name}"}

        registry = create_default_registry()
        tool = registry.get_tool(internal_name)
        if not tool:
            return {"success": False, "error": f"Internal tool not found: {internal_name}"}

        tool_args = dict(args)
        project_id = tool_args.pop("project_id", "")
        chapter_number = tool_args.pop("chapter_number", None)

        if internal_name == "generate":
            writing_notes = tool_args.pop("writing_notes", "")
            tool_args.pop("preset", None)
            tool_args.setdefault("writer_prompt", writing_notes or "请生成本章内容。")

        from ..db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            context = AgentToolContext(
                session=session,
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=0,
            )

            if internal_name == "character_state" and "action" not in tool_args:
                tool_args["action"] = "get_all_states"
            if internal_name == "foreshadowing" and "action" not in tool_args:
                tool_args["action"] = "get_unresolved"

            result = await tool.call(tool_args, context)
            return {"success": result.success, "data": result.data, "error": result.error}

    @staticmethod
    def _ok(req_id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result or {}}

    @staticmethod
    def _error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def run_stdio() -> None:
    """Run MCP server over stdio (JSON-RPC line protocol)."""
    server = MCPServer()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout,
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

    logger.info("MCP server started (stdio transport)")

    while True:
        line = await reader.readline()
        if not line:
            break

        try:
            request = json.loads(line.decode("utf-8").strip())
            response = await server.handle_request(request)
            response_bytes = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
            writer.write(response_bytes)
            await writer.drain()
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received: %s", line[:200])
        except Exception as e:
            logger.error("MCP request error: %s", e, exc_info=True)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Arboris-Novel MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(run_stdio())
    else:
        logger.info("HTTP transport not yet implemented, use stdio for now")
        sys.exit(1)


if __name__ == "__main__":
    main()
