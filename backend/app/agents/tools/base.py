# AIMETA P=Agent工具基类|R=工具抽象层|NR=所有Agent工具的基类定义|E=AgentTool|X=internal|A=抽象基类|D=abc
"""Agent tool base class and shared types."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    is_read_only: bool = True
    is_concurrency_safe: bool = True


@dataclass
class ValidationResult:
    valid: bool
    error: Optional[str] = None


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    token_estimate: int = 0


@dataclass
class AgentToolContext:
    session: AsyncSession
    project_id: str
    chapter_number: Optional[int] = None
    user_id: int = 0
    config: Dict[str, Any] = field(default_factory=dict)


class AgentTool(ABC):
    """Base class for all agent-callable tools."""

    definition: ToolDefinition

    def validate_input(self, args: dict) -> ValidationResult:
        required = self.definition.input_schema.get("required", [])
        properties = self.definition.input_schema.get("properties", {})
        for key in required:
            if key not in args:
                return ValidationResult(valid=False, error=f"Missing required parameter: {key}")
        for key in args:
            if key not in properties:
                return ValidationResult(valid=False, error=f"Unknown parameter: {key}")
        return ValidationResult(valid=True)

    @abstractmethod
    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        ...

    def to_openai_tool_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.definition.name,
                "description": self.definition.description,
                "parameters": self.definition.input_schema,
            },
        }
