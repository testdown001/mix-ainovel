from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Dict, Optional


class GenerationTelemetryService:
    """统一封装生成过程中的事件发射、阶段管理和耗时记录。"""

    def __init__(self, emit_stream: Callable[[str, Optional[Dict[str, Any]]], Awaitable[None]]):
        self._emit_stream = emit_stream
        self._stage_timings_ms: Dict[str, int] = {}

    @property
    def stage_timings_ms(self) -> Dict[str, int]:
        """获取阶段耗时记录（毫秒）。"""
        return self._stage_timings_ms

    def mark_stage(self, stage_name: str, started_at: float) -> None:
        """记录阶段耗时。

        Args:
            stage_name: 阶段名称
            started_at: 阶段开始时间（time.perf_counter()）
        """
        self._stage_timings_ms[stage_name] = int((time.perf_counter() - started_at) * 1000)

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
