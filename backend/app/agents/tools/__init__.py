# AIMETA P=工具包入口|R=导出所有Agent工具|NR=提供统一入口和默认注册|E=tools|X=internal|A=包入口|D=none
"""Agent tools package — all tool implementations and the registry."""
from __future__ import annotations

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult, ValidationResult
from .registry import ToolRegistry

from .character_state import CharacterStateTool
from .consistency_check import ConsistencyCheckTool
from .entity_registry import EntityRegistryTool
from .evidence_grade import EvidenceGradeTool
from .foreshadowing import ForeshadowingTool
from .generate import GenerateTool
from .history_context import HistoryContextTool
from .power_system import PowerSystemTool
from .prompt_assembly import PromptAssemblyTool
from .rag_retrieve import RagRetrieveTool
from .review import ReviewTool
from .skill_apply import SkillApplyTool

ALL_TOOLS: list[type[AgentTool]] = [
    RagRetrieveTool,
    ConsistencyCheckTool,
    CharacterStateTool,
    ForeshadowingTool,
    PowerSystemTool,
    ReviewTool,
    SkillApplyTool,
    HistoryContextTool,
    EntityRegistryTool,
    GenerateTool,
    PromptAssemblyTool,
    EvidenceGradeTool,
]


def create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry with all built-in tools registered."""
    registry = ToolRegistry()
    for tool_cls in ALL_TOOLS:
        registry.register(tool_cls())
    return registry


__all__ = [
    "AgentTool",
    "AgentToolContext",
    "ToolDefinition",
    "ToolResult",
    "ValidationResult",
    "ToolRegistry",
    "ALL_TOOLS",
    "create_default_registry",
    "CharacterStateTool",
    "ConsistencyCheckTool",
    "EntityRegistryTool",
    "EvidenceGradeTool",
    "ForeshadowingTool",
    "GenerateTool",
    "HistoryContextTool",
    "PowerSystemTool",
    "PromptAssemblyTool",
    "RagRetrieveTool",
    "ReviewTool",
    "SkillApplyTool",
]
