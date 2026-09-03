from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Dict, Optional

from ..utils.tracing import emit_span, new_trace_id


_active_llm_metrics: ContextVar[Optional[list[Dict[str, Any]]]] = ContextVar(
    "active_generation_llm_metrics",
    default=None,
)


def record_generation_llm_call(metric: Dict[str, Any]) -> None:
    """把一次 LLM 调用归入当前章节。

    ContextVar 让同一进程内并发生成的章节互不串数据；未处于章节流水线时静默忽略，
    因而后台通道测试、灵感对话等调用不会污染章节性能数据。
    """
    metrics = _active_llm_metrics.get()
    if metrics is not None:
        metrics.append(dict(metric))


class GenerationTelemetryService:
    """统一封装生成过程中的事件发射、阶段管理和耗时记录。"""

    def __init__(self, emit_stream: Callable[[str, Optional[Dict[str, Any]]], Awaitable[None]]):
        self._emit_stream = emit_stream
        self._stage_timings_ms: Dict[str, int] = {}
        # 每次生成任务一个 trace_id；阶段 span 共享它，便于按 trace 串联排障
        self.trace_id: str = new_trace_id()
        self._trace_attrs: Dict[str, Any] = {}
        self._span_seq: int = 0
        self._llm_calls: list[Dict[str, Any]] = []
        _active_llm_metrics.set(self._llm_calls)

    @property
    def stage_timings_ms(self) -> Dict[str, int]:
        """获取阶段耗时记录（毫秒）。"""
        return self._stage_timings_ms

    @property
    def llm_metrics(self) -> Dict[str, Any]:
        """返回可持久化的章节级 LLM 性能快照（含逐调用明细与汇总）。"""
        calls = [dict(item) for item in self._llm_calls]
        total_duration_ms = sum(int(item.get("duration_ms") or 0) for item in calls)
        completion_tokens = sum(int(item.get("completion_tokens") or 0) for item in calls)
        first_token_values = [
            int(item["first_token_ms"])
            for item in calls
            if item.get("first_token_ms") is not None
        ]
        return {
            "summary": {
                "call_count": len(calls),
                "success_count": sum(item.get("status") == "success" for item in calls),
                "failure_count": sum(item.get("status") != "success" for item in calls),
                "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in calls),
                "completion_tokens": completion_tokens,
                "retry_count": sum(int(item.get("retry_count") or 0) for item in calls),
                "fallback_count": sum(item.get("api_type") == "fallback" for item in calls),
                "compatibility_fallback_count": sum(
                    int(item.get("compatibility_fallback_count") or 0) for item in calls
                ),
                "total_llm_duration_ms": total_duration_ms,
                "first_token_ms": min(first_token_values) if first_token_values else None,
                "output_tokens_per_second": round(
                    completion_tokens / (total_duration_ms / 1000), 2
                ) if total_duration_ms > 0 else 0.0,
            },
            "calls": calls,
        }

    def set_trace_context(self, **attrs: Any) -> None:
        """挂载 trace 级上下文属性（如 project_id / chapter_number / preset），随每个 span 输出。"""
        for key, value in attrs.items():
            if value is not None:
                self._trace_attrs[key] = value

    def mark_stage(self, stage_name: str, started_at: float) -> None:
        """记录阶段耗时，并发射一条结构化 span（轻量 tracing）。

        Args:
            stage_name: 阶段名称
            started_at: 阶段开始时间（time.perf_counter()）
        """
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        self._stage_timings_ms[stage_name] = duration_ms
        emit_span(
            name=stage_name,
            duration_ms=duration_ms,
            trace_id=self.trace_id,
            attributes={**self._trace_attrs, "seq": self._span_seq},
        )
        self._span_seq += 1

    async def emit_stage(self, stage: str, message: Optional[str] = None, chapter_number: Optional[int] = None) -> None:
        """发送阶段事件。

        Args:
            stage: 阶段名称
            message: 阶段消息（可选，默认使用 stage）
            chapter_number: 章节号（可选）
        """
        payload = {
            "stage": stage,
            "message": message or stage,
        }
        if chapter_number is not None:
            payload["chapter_number"] = chapter_number
        await self._emit_stream("stage", payload)

    async def emit_text_delta(self, delta: str, stage: str, chapter_number: Optional[int] = None) -> None:
        """发送流式文本增量事件。

        Args:
            delta: 文本增量
            stage: 当前阶段
            chapter_number: 章节号（可选）
        """
        payload = {
            "delta": delta,
            "stage": stage,
        }
        if chapter_number is not None:
            payload["chapter_number"] = chapter_number
        await self._emit_stream("text_delta", payload)

    async def emit_completed(self, chapter_number: Optional[int] = None) -> None:
        """发送完成事件。

        Args:
            chapter_number: 章节号（可选）
        """
        await self.emit_stage("completed", "章节生成完成", chapter_number)

    # ========== 中间产物事件 ==========

    async def emit_context_plan(self, context_plan: Dict[str, Any]) -> None:
        await self._emit_middle_product("context_plan", context_plan)

    async def emit_mission(self, mission: Dict[str, Any]) -> None:
        await self._emit_middle_product("mission", mission)

    async def emit_rag(self, rag_payload: Dict[str, Any]) -> None:
        await self._emit_middle_product("rag", rag_payload)

    async def emit_foreshadowing(self, foreshadowing_payload: Dict[str, Any]) -> None:
        await self._emit_middle_product("foreshadowing", foreshadowing_payload)

    async def emit_context(self, context_payload: Dict[str, Any]) -> None:
        await self._emit_middle_product("context", context_payload)

    async def emit_retrieval_evidence_summary(self, summary: Dict[str, Any]) -> None:
        await self._emit_middle_product("retrieval_evidence_summary", summary)

    async def emit_evidence_grade(self, grade_report: Dict[str, Any]) -> None:
        await self._emit_middle_product("evidence_grade", grade_report)

    async def emit_prompt_compile_summary(self, summary: Dict[str, Any]) -> None:
        await self._emit_middle_product("prompt_compile_summary", summary)

    async def emit_creative_memory_receipt(self, receipt: Dict[str, Any]) -> None:
        """记录本次生成实际采用的已确认创作记忆，便于前端解释与审计。"""
        await self._emit_middle_product("creative_memory_receipt", receipt)

    async def emit_verification_report(self, report: Dict[str, Any]) -> None:
        await self._emit_middle_product("verification_report", report)

    async def _emit_middle_product(self, event_type: str, data: Dict[str, Any]) -> None:
        await self._emit_stream(
            "middle_product",
            {
                "type": event_type,
                "data": data,
            },
        )
