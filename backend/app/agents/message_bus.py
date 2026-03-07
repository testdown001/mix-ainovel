# AIMETA P=Agent消息总线|R=Agent间消息传递|NR=基于内存的消息队列|E=AgentMessageBus|X=internal|A=消息服务|D=asyncio
"""Agent 消息总线实现"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentMessageBus:
    """Agent 消息总线（内存实现）"""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._task_queues: Dict[str, asyncio.Queue] = {}
        self._running = False
        self._process_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """初始化"""
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("AgentMessageBus initialized")

    async def shutdown(self) -> None:
        """关闭"""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("AgentMessageBus shutdown")

    async def publish(self, channel: str, message: Dict[str, Any]) -> None:
        """发布消息"""
        task_id = message.get("task_id")
        if task_id:
            await self._persist_to_queue(task_id, message)

        for handler in self._handlers.get(channel, []):
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error for {channel}: {e}")

    async def subscribe(self, agent_name: str, handler: Callable) -> None:
        """订阅消息"""
        channel = f"agent.{agent_name}"
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)
        logger.debug(f"Subscribed {agent_name} to {channel}")

    async def subscribe_broadcast(self, handler: Callable) -> None:
        """订阅广播消息"""
        if "agent.broadcast" not in self._handlers:
            self._handlers["agent.broadcast"] = []
        self._handlers["agent.broadcast"].append(handler)

    async def wait_for_message(
        self,
        task_id: str,
        timeout: float = 300
    ) -> Optional[Dict[str, Any]]:
        """等待特定任务的消息"""
        if task_id not in self._task_queues:
            self._task_queues[task_id] = asyncio.Queue()

        try:
            return await asyncio.wait_for(
                self._task_queues[task_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for task {task_id}")
            return None

    async def _persist_to_queue(self, task_id: str, message: Dict) -> None:
        """持久化消息到任务队列"""
        if task_id not in self._task_queues:
            self._task_queues[task_id] = asyncio.Queue()
        await self._task_queues[task_id].put(message)

    async def _process_loop(self) -> None:
        """消息处理循环"""
        while self._running:
            await asyncio.sleep(0.1)

    def clear_task_queue(self, task_id: str) -> None:
        """清除任务队列"""
        if task_id in self._task_queues:
            del self._task_queues[task_id]
