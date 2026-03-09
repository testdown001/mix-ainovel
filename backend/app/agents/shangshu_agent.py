# AIMETA P=尚书省Agent|R=调度协调|NR=协调兵部吏部户部执行任务|E=ShangshuAgent|X=internal|A=Agent实现|D=asyncio
"""尚书省 Agent - 调度协调"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from .message import AgentContext, AgentMessageType, AgentResult


class ShangshuAgent(BaseAgent):
    """
    尚书省 Agent - 调度协调

    职责：
    1. 接收中书省的写作任务
    2. 协调兵部、吏部、户部执行
    3. 汇总结果
    4. 转发给门下省审核
    """

    AGENT_NAME = "shangshu"

    def __init__(self, agent_id: str, session):
        super().__init__(agent_id, session)
        self._pending_versions: Dict[str, List[Dict[str, Any]]] = {}
        self._version_events: Dict[str, asyncio.Event] = {}

    async def process(self, context: AgentContext) -> AgentResult:
        await self.emit_stage("agent:shangshu:start", "开始调度兵部生成章节")

        mission = context.mission
        writing_prompt = context.metadata.get("writing_prompt")
        context_data = context.metadata.get("context_data", {})
        version_count = context.config.get("version_count", 3)

        await self._setup_message_handlers(context.task_id)

        await self._dispatch_bingbu(
            context.task_id,
            context.project_id,
            context.chapter_number,
            writing_prompt,
            version_count,
        )

        await self.emit_stage("agent:shangshu:waiting", "等待兵部生成版本...")

        chapter_versions = await self._wait_for_versions(context.task_id, timeout=300)

        if not chapter_versions:
            return AgentResult(
                status="failed",
                error="章节生成超时"
            )

        if context.config.get("enable_consistency_check"):
            await self.emit_stage("agent:shangshu:consistency", "调度吏部进行一致性检查")
            await self._dispatch_libu(
                context.task_id,
                context.project_id,
                context.chapter_number,
                chapter_versions,
            )

        result = await self._aggregate_results(chapter_versions)

        await self.emit_stage("agent:shangshu:done", f"收到 {len(chapter_versions)} 个版本，转交门下省审核")

        await self._dispatch_menxia(
            context.task_id,
            context.project_id,
            context.chapter_number,
            result,
        )

        return AgentResult(
            status="delegated",
            output={"versions": chapter_versions},
            next_agent="menxia"
        )

    async def _setup_message_handlers(self, task_id: str) -> None:
        """设置消息处理器"""
        async def handle_version_ready(message: Dict[str, Any]) -> None:
            if message.get("task_id") != task_id:
                return
            payload = message.get("payload", {})
            versions = payload.get("versions", [])
            self._pending_versions[task_id] = versions
            if task_id in self._version_events:
                self._version_events[task_id].set()

        await self.message_bus.subscribe("bingbu", handle_version_ready)

    async def _dispatch_bingbu(
        self,
        task_id: str,
        project_id: str,
        chapter_number: Optional[int],
        writing_prompt: str,
        version_count: int,
    ) -> None:
        """调度兵部生成章节"""
        await self.send_message(
            recipient="bingbu",
            message_type=AgentMessageType.CHAPTER_GENERATE_REQUEST.value,
            payload={
                "writing_prompt": writing_prompt,
                "version_count": version_count,
            },
            task_id=task_id,
            project_id=project_id,
            chapter_number=chapter_number,
        )

    async def _dispatch_libu(
        self,
        task_id: str,
        project_id: str,
        chapter_number: Optional[int],
        versions: List[Dict[str, Any]],
    ) -> None:
        """调度吏部检查一致性"""
        await self.send_message(
            recipient="libu",
            message_type=AgentMessageType.CONTEXT_REQUEST.value,
            payload={
                "action": "check_consistency",
                "versions": versions,
            },
            task_id=task_id,
            project_id=project_id,
            chapter_number=chapter_number,
        )

    async def _dispatch_menxia(
        self,
        task_id: str,
        project_id: str,
        chapter_number: Optional[int],
        result: Dict[str, Any],
    ) -> None:
        """调度门下省审核"""
        await self.send_message(
            recipient="menxia",
            message_type=AgentMessageType.REVIEW_REQUEST.value,
            payload={"chapter": result},
            task_id=task_id,
            project_id=project_id,
            chapter_number=chapter_number,
        )

    async def _wait_for_versions(
        self,
        task_id: str,
        timeout: float = 300
    ) -> List[Dict[str, Any]]:
        """等待版本生成"""
        event = asyncio.Event()
        self._version_events[task_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

        return self._pending_versions.get(task_id, [])

    async def _aggregate_results(self, versions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """汇总结果"""
        if not versions:
            return {}

        best_version = versions[0]

        return {
            "content": best_version.get("content", ""),
            "versions": versions,
            "selected_version": best_version.get("version_id"),
        }
