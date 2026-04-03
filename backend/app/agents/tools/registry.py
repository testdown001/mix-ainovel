# AIMETA P=工具注册表|R=集中管理所有Agent工具|NR=提供工具注册/查找/Schema输出|E=ToolRegistry|X=internal|A=注册表|D=none
"""Central registry for agent tools."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .base import AgentTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Manages all available agent tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        name = tool.definition.name
        if name in self._tools:
            logger.warning("Tool %s is already registered, overwriting", name)
        self._tools[name] = tool
        logger.debug("Registered tool: %s", name)

    def get_tool(self, name: str) -> Optional[AgentTool]:
        return self._tools.get(name)

    def get_tools(self, names: Optional[List[str]] = None) -> List[AgentTool]:
        if names is None:
            return list(self._tools.values())
        return [self._tools[n] for n in names if n in self._tools]

    def get_all_tool_schemas(self, names: Optional[List[str]] = None) -> List[dict]:
        return [t.to_openai_tool_schema() for t in self.get_tools(names)]

    def list_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
