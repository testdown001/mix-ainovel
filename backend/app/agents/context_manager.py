# AIMETA P=上下文管理器|R=Token预算追踪与压缩|NR=管理智能体循环的上下文窗口|E=AgentContextManager|X=internal|A=引擎组件|D=asyncio
"""
Context window management for the agentic loop.

Components:
- TokenBudgetTracker: tracks cumulative token usage per conversation
- ContextCompactor: summarizes history when approaching limits
- ToolResultBudget: truncates oversized tool results
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_AVG_CHARS_PER_TOKEN_ZH = 1.5
_AVG_CHARS_PER_TOKEN_EN = 4.0


def estimate_tokens(text: str) -> int:
    """Fast heuristic token estimation for mixed CJK/Latin text."""
    if not text:
        return 0
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f')
    latin_count = len(text) - cjk_count
    return int(cjk_count / _AVG_CHARS_PER_TOKEN_ZH + latin_count / _AVG_CHARS_PER_TOKEN_EN)


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        content = msg.get("content") or ""
        total += estimate_tokens(content) + 4  # per-message overhead
        if msg.get("tool_calls"):
            total += estimate_tokens(json.dumps(msg["tool_calls"], ensure_ascii=False))
    return total


@dataclass
class ContextBudget:
    max_tokens: int = 120000
    compact_threshold: float = 0.75
    reserved_for_output: int = 8000
    max_tool_result_tokens: int = 4000

    @property
    def compact_trigger(self) -> int:
        return int(self.max_tokens * self.compact_threshold)

    @property
    def available_for_context(self) -> int:
        return self.max_tokens - self.reserved_for_output


@dataclass
class BudgetStatus:
    used_tokens: int
    max_tokens: int
    utilization: float
    needs_compaction: bool
    messages_count: int


class TokenBudgetTracker:
    """Tracks token usage and signals when compaction is needed."""

    def __init__(self, budget: Optional[ContextBudget] = None):
        self.budget = budget or ContextBudget()
        self._cumulative_input: int = 0
        self._cumulative_output: int = 0

    def check(self, messages: List[Dict[str, Any]]) -> BudgetStatus:
        used = estimate_messages_tokens(messages)
        utilization = used / self.budget.available_for_context if self.budget.available_for_context > 0 else 1.0
        return BudgetStatus(
            used_tokens=used,
            max_tokens=self.budget.available_for_context,
            utilization=min(utilization, 1.0),
            needs_compaction=used >= self.budget.compact_trigger,
            messages_count=len(messages),
        )

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        self._cumulative_input += input_tokens
        self._cumulative_output += output_tokens

    @property
    def total_tokens_used(self) -> int:
        return self._cumulative_input + self._cumulative_output


class ContextCompactor:
    """Compresses conversation history when approaching context limits."""

    COMPACT_SYSTEM_PROMPT = (
        "请将以下对话历史压缩为一份简明摘要，保留关键事实、决策和结果。"
        "用中文输出，不超过500字。只输出摘要内容。"
    )

    async def compact(
        self,
        messages: List[Dict[str, Any]],
        budget: ContextBudget,
        llm_service: Any,
        user_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """Compress older messages into a summary, keeping recent ones intact.

        Strategy: keep the system prompt (index 0), the last 4 messages,
        and summarize everything in between.
        """
        if len(messages) <= 5:
            return messages

        system_msg = messages[0] if messages[0].get("role") == "system" else None
        start_idx = 1 if system_msg else 0
        keep_recent = 4

        to_compress = messages[start_idx:-keep_recent]
        to_keep = messages[-keep_recent:]

        if not to_compress:
            return messages

        history_text = self._serialize_messages(to_compress)

        try:
            summary = await llm_service.get_llm_response(
                system_prompt=self.COMPACT_SYSTEM_PROMPT,
                conversation_history=[{"role": "user", "content": history_text}],
                temperature=0.2,
                user_id=user_id,
                timeout=60.0,
                response_format=None,
                max_tokens=1000,
            )
        except Exception as e:
            logger.warning("Context compaction failed, falling back to truncation: %s", e)
            summary = self._truncate_summary(to_compress)

        compacted: List[Dict[str, Any]] = []
        if system_msg:
            compacted.append(system_msg)

        compacted.append({
            "role": "user",
            "content": f"[历史对话摘要]\n{summary}",
        })
        compacted.extend(to_keep)

        logger.info(
            "Context compacted: %d messages → %d messages (compressed %d)",
            len(messages), len(compacted), len(to_compress),
        )

        return compacted

    @staticmethod
    def _serialize_messages(messages: List[Dict[str, Any]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "tool":
                tool_id = msg.get("tool_call_id", "?")
                parts.append(f"[工具结果 {tool_id}] {content[:500]}")
            elif role == "assistant" and msg.get("tool_calls"):
                calls = msg["tool_calls"]
                call_summary = ", ".join(
                    tc.get("function", {}).get("name", "?") for tc in calls
                )
                parts.append(f"[助手调用工具: {call_summary}]")
                if content:
                    parts.append(f"[助手文本] {content[:300]}")
            else:
                parts.append(f"[{role}] {content[:500]}")
        return "\n".join(parts)

    @staticmethod
    def _truncate_summary(messages: List[Dict[str, Any]]) -> str:
        """Fallback: extract key info without LLM."""
        parts = []
        for msg in messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and data.get("error"):
                        parts.append(f"工具调用失败: {data['error'][:100]}")
                except (json.JSONDecodeError, TypeError):
                    pass
            elif msg.get("role") == "assistant" and msg.get("content"):
                parts.append(msg["content"][:200])
        return "\n".join(parts[-5:]) if parts else "（无可用摘要）"


class ToolResultBudget:
    """Truncates oversized tool results to fit within budget."""

    def __init__(self, max_tokens_per_result: int = 4000):
        self.max_tokens_per_result = max_tokens_per_result

    def apply(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                tokens = estimate_tokens(content)
                if tokens > self.max_tokens_per_result:
                    truncated = self._truncate_content(content, self.max_tokens_per_result)
                    msg = {**msg, "content": truncated}
                    logger.debug(
                        "Truncated tool result from ~%d to ~%d tokens",
                        tokens, estimate_tokens(truncated),
                    )
            result.append(msg)
        return result

    @staticmethod
    def _truncate_content(content: str, max_tokens: int) -> str:
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                truncated = {}
                budget_remaining = max_tokens
                for key, value in data.items():
                    serialized = json.dumps(value, ensure_ascii=False, default=str)
                    val_tokens = estimate_tokens(serialized)
                    if budget_remaining - val_tokens > 0:
                        truncated[key] = value
                        budget_remaining -= val_tokens
                    else:
                        str_val = str(value)
                        max_chars = int(budget_remaining * _AVG_CHARS_PER_TOKEN_ZH)
                        truncated[key] = str_val[:max_chars] + "...[truncated]"
                        break
                return json.dumps(truncated, ensure_ascii=False, default=str)
        except (json.JSONDecodeError, TypeError):
            pass

        max_chars = int(max_tokens * _AVG_CHARS_PER_TOKEN_ZH)
        return content[:max_chars] + "...[truncated]"


class AgentContextManager:
    """High-level manager combining budget tracking, compaction, and result budgeting."""

    def __init__(self, budget: Optional[ContextBudget] = None):
        self.budget = budget or ContextBudget()
        self.tracker = TokenBudgetTracker(self.budget)
        self.compactor = ContextCompactor()
        self.result_budget = ToolResultBudget(self.budget.max_tool_result_tokens)

    async def check_and_compact(
        self,
        messages: List[Dict[str, Any]],
        llm_service: Any,
        user_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """Check token budget; compact if threshold exceeded."""
        messages = self.result_budget.apply(messages)

        status = self.tracker.check(messages)
        if status.needs_compaction:
            logger.info(
                "Context budget at %.0f%% (%d/%d tokens), compacting...",
                status.utilization * 100, status.used_tokens, status.max_tokens,
            )
            messages = await self.compactor.compact(
                messages, self.budget, llm_service, user_id,
            )

        return messages

    def get_status(self, messages: List[Dict[str, Any]]) -> BudgetStatus:
        return self.tracker.check(messages)
