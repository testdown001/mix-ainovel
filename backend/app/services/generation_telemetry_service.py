from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional


class GenerationTelemetryService:
    """统一封装生成过程中的 middle_product 事件发射。"""

    def __init__(self, emit_stream: Callable[[str, Optional[Dict[str, Any]]], Awaitable[None]]):
        self._emit_stream = emit_stream

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
