# AIMETA P=智能体循环引擎|R=核心推理-执行循环|NR=LLM自主决定工具调用|E=AgenticLoop|X=internal|A=引擎|D=asyncio
"""
Agentic loop engine — the core reasoning/execution loop that drives tool-using agents.

Inspired by Claude Code's queryLoop architecture:
  while True:
    response = LLM(messages, tools)
    if no tool_calls in response: break
    execute tool_calls → append results → continue
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .context_manager import AgentContextManager, ContextBudget
from .tools.base import AgentTool, AgentToolContext, ToolResult
from .tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgenticLoopState:
    messages: List[Dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tool_calls_made: int = 0
    started_at: float = field(default_factory=time.perf_counter)
    transition_reason: Optional[str] = None


@dataclass
class AgenticLoopConfig:
    max_turns: int = 15
    max_tool_calls: int = 50
    system_prompt: str = ""
    tool_names: Optional[List[str]] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: float = 1500.0


@dataclass
class AgenticLoopResult:
    content: str
    state: AgenticLoopState
    tool_history: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "completed"


class AgenticLoop:
    """Core agentic loop: LLM reasons, calls tools, loop until done."""

    def __init__(
        self,
        session: AsyncSession,
        tool_registry: ToolRegistry,
        config: AgenticLoopConfig,
        *,
        project_id: str,
        chapter_number: Optional[int] = None,
        user_id: int = 0,
        agent_config: Optional[Dict[str, Any]] = None,
        stream_handler: Optional[Callable] = None,
        context_budget: Optional[ContextBudget] = None,
    ):
        self.session = session
        self.tool_registry = tool_registry
        self.config = config
        self.project_id = project_id
        self.chapter_number = chapter_number
        self.user_id = user_id
        self.agent_config = agent_config or {}
        self.stream_handler = stream_handler
        self.context_manager = AgentContextManager(context_budget)

        self._tool_context = AgentToolContext(
            session=session,
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            config=agent_config or {},
        )

    async def run(self, user_message: str) -> AgenticLoopResult:
        from ..services.llm_service import LLMService

        llm_service = LLMService(self.session)
        state = AgenticLoopState()
        tool_history: List[Dict[str, Any]] = []

        state.messages.append({"role": "system", "content": self.config.system_prompt})
        state.messages.append({"role": "user", "content": user_message})

        tool_schemas = self.tool_registry.get_all_tool_schemas(self.config.tool_names)

        while state.turn_count < self.config.max_turns:
            state.turn_count += 1

            await self._emit_event("loop_iteration", {
                "turn": state.turn_count,
                "max_turns": self.config.max_turns,
                "tool_calls_so_far": state.tool_calls_made,
            })

            state.messages = await self.context_manager.check_and_compact(
                state.messages, llm_service, self.user_id,
            )

            try:
                response = await llm_service.chat_with_tools(
                    messages=state.messages,
                    tools=tool_schemas,
                    temperature=self.config.temperature,
                    user_id=self.user_id,
                    timeout=self.config.timeout,
                    max_tokens=self.config.max_tokens,
                )
            except Exception as e:
                logger.error("LLM call failed in agentic loop turn %d: %s", state.turn_count, e)
                state.transition_reason = f"llm_error: {e}"
                return AgenticLoopResult(
                    content=f"LLM call failed: {e}",
                    state=state,
                    tool_history=tool_history,
                    finish_reason="error",
                )

            content = response.get("content")
            tool_calls = response.get("tool_calls", [])
            finish_reason = response.get("finish_reason", "stop")

            if not tool_calls:
                state.transition_reason = "no_tool_calls"
                return AgenticLoopResult(
                    content=content or "",
                    state=state,
                    tool_history=tool_history,
                    finish_reason="completed",
                )

            assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = tool_calls
            state.messages.append(assistant_msg)

            tool_results = await self._execute_tool_calls(tool_calls, tool_history, state)

            for tc, result in zip(tool_calls, tool_results):
                result_content = json.dumps(result.data if result.success else {"error": result.error}, ensure_ascii=False, default=str)
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_content,
                })

            if state.tool_calls_made >= self.config.max_tool_calls:
                state.transition_reason = "max_tool_calls_reached"
                return AgenticLoopResult(
                    content=content or "",
                    state=state,
                    tool_history=tool_history,
                    finish_reason="max_tool_calls",
                )

        state.transition_reason = "max_turns_reached"
        last_content = ""
        for msg in reversed(state.messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                last_content = msg["content"]
                break

        return AgenticLoopResult(
            content=last_content,
            state=state,
            tool_history=tool_history,
            finish_reason="max_turns",
        )

    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        tool_history: List[Dict[str, Any]],
        state: AgenticLoopState,
    ) -> List[ToolResult]:
        concurrent_indices: List[int] = []
        serial_indices: List[int] = []
        resolved_tools: List[Optional[AgentTool]] = []

        for i, tc in enumerate(tool_calls):
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            tool = self.tool_registry.get_tool(tool_name)
            resolved_tools.append(tool)
            if tool and tool.definition.is_concurrency_safe:
                concurrent_indices.append(i)
            else:
                serial_indices.append(i)

        results: List[Optional[ToolResult]] = [None] * len(tool_calls)

        if concurrent_indices:
            tasks = [
                self._execute_single_tool(tool_calls[i], resolved_tools[i], tool_history, state)
                for i in concurrent_indices
            ]
            concurrent_results = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, r in zip(concurrent_indices, concurrent_results):
                if isinstance(r, Exception):
                    results[idx] = ToolResult(success=False, error=str(r))
                else:
                    results[idx] = r

        for idx in serial_indices:
            result = await self._execute_single_tool(tool_calls[idx], resolved_tools[idx], tool_history, state)
            results[idx] = result

        return results  # type: ignore[return-value]

    async def _execute_single_tool(
        self,
        tool_call: Dict[str, Any],
        tool: Optional[AgentTool],
        tool_history: List[Dict[str, Any]],
        state: AgenticLoopState,
    ) -> ToolResult:
        func = tool_call.get("function", {})
        tool_name = func.get("name", "unknown")
        raw_args = func.get("arguments", "{}")

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            return ToolResult(success=False, error=f"Invalid JSON arguments: {raw_args[:200]}")

        if tool is None:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

        validation = tool.validate_input(args)
        if not validation.valid:
            return ToolResult(success=False, error=f"Validation failed: {validation.error}")

        await self._emit_event("tool_call", {
            "tool": tool_name,
            "args_summary": {k: type(v).__name__ for k, v in args.items()},
        })

        started = time.perf_counter()
        try:
            result = await tool.call(args, self._tool_context)
        except Exception as e:
            logger.error("Tool %s execution error: %s", tool_name, e, exc_info=True)
            result = ToolResult(success=False, error=str(e))

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        state.tool_calls_made += 1

        history_entry = {
            "tool": tool_name,
            "args": args,
            "success": result.success,
            "elapsed_ms": elapsed_ms,
        }
        if not result.success:
            history_entry["error"] = result.error
        tool_history.append(history_entry)

        await self._emit_event("tool_result", {
            "tool": tool_name,
            "success": result.success,
            "elapsed_ms": elapsed_ms,
        })

        logger.info(
            "Tool %s completed: success=%s elapsed=%dms",
            tool_name, result.success, elapsed_ms,
        )

        return result

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        if not self.stream_handler:
            return
        import inspect

        if event_type == "tool_call":
            tool_name = data.get("tool", "unknown")
            message = f"调用工具: {tool_name}"
        elif event_type == "tool_result":
            tool_name = data.get("tool", "unknown")
            success = data.get("success", True)
            elapsed = data.get("elapsed_ms", 0)
            status = "成功" if success else "失败"
            message = f"工具 {tool_name} {status} ({elapsed}ms)"
        elif event_type == "loop_iteration":
            turn = data.get("turn", 0)
            max_turns = data.get("max_turns", 0)
            message = f"推理迭代 {turn}/{max_turns}"
        elif event_type == "context_compact":
            message = "上下文压缩已执行"
        else:
            message = str(data)

        event = {"event": "stage", "stage": event_type, "message": message}
        try:
            result = self.stream_handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            logger.debug("Stream handler error (ignored): %s", e)
