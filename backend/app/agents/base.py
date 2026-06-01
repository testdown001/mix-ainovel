# AIMETA P=Agent基类|R=所有Agent的基类|NR=提供通用方法和接口|E=BaseAgent|X=internal|A=抽象基类|D=abc
"""Agent 基类定义"""
from __future__ import annotations

import inspect
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.llm_service import LLMService
from ..services.prompt_service import PromptService
from .message import AgentCapability, AgentContext, AgentResult

if TYPE_CHECKING:
    from .message_bus import AgentMessageBus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""

    AGENT_NAME: str = "base"
    AGENT_VERSION: str = "1.0.0"

    # Agent 名称映射到中文名称
    STAGE_NAMES = {
        "taizi": "太子分拣",
        "zhongshu": "中书规划",
        "bingbu": "兵部生成",
        "hubu": "户部技能",
        "menxia": "门下审核",
    }

    def __init__(self, agent_id: str, session: AsyncSession):
        self.agent_id = agent_id
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.message_bus: Optional[AgentMessageBus] = None

        # 奏折相关
        self._archive_service = None
        self._current_archive_id: Optional[int] = None
        self._stage_start_time: float = 0

        # 流式事件推送
        self._stream_handler: Optional[Callable] = None

        self._capabilities: Dict[str, AgentCapability] = {}
        self._register_capabilities()

    def set_archive_service(self, archive_service) -> None:
        """设置档案服务"""
        self._archive_service = archive_service

    def set_archive_id(self, archive_id: int) -> None:
        """设置当前档案ID"""
        self._current_archive_id = archive_id

    def set_stream_handler(self, handler: Optional[Callable]) -> None:
        """设置流式事件推送回调"""
        self._stream_handler = handler

    async def emit_stage(self, stage: str, message: str) -> None:
        """向前端推送阶段事件（SSE stage 格式）"""
        if not self._stream_handler:
            return
        data = {"event": "stage", "stage": stage, "message": message}
        try:
            result = self._stream_handler(data)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            logger.debug("emit_stage callback error (ignored): %s", e)

    def _start_stage(self) -> None:
        """开始记录阶段"""
        self._stage_start_time = time.perf_counter()

    async def _complete_stage(
        self,
        status: str = "completed",
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """完成阶段记录"""
        if not self._archive_service or not self._current_archive_id:
            return

        duration_ms = int((time.perf_counter() - self._stage_start_time) * 1000)
        stage_name = self.STAGE_NAMES.get(self.AGENT_NAME, self.AGENT_NAME)

        try:
            await self._archive_service.add_workflow_stage(
                archive_id=self._current_archive_id,
                stage=stage_name,
                agent=self.AGENT_NAME,
                status=status,
                duration_ms=duration_ms,
                input_data=input_data,
                output_data=output_data,
            )
        except Exception as e:
            logger.warning(f"Failed to record stage: {e}")

    @abstractmethod
    async def process(self, context: AgentContext) -> AgentResult:
        """处理任务（子类必须实现）"""
        pass

    async def initialize(self) -> None:
        """初始化 Agent"""
        logger.info(f"Initializing agent: {self.AGENT_NAME}")
        await self._load_prompts()
        await self._load_config()

    async def cleanup(self) -> None:
        """清理资源"""
        logger.info(f"Cleaning up agent: {self.AGENT_NAME}")

    # ========== 消息发送 ==========

    async def send_message(
        self,
        recipient: str,
        message_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
    ) -> None:
        """发送消息给其他 Agent"""
        if not self._can_send_to(recipient):
            raise PermissionError(
                f"Agent {self.AGENT_NAME} cannot send message to {recipient}"
            )

        from .message import AgentMessage

        message = AgentMessage(
            sender=self.AGENT_NAME,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            task_id=task_id,
            project_id=project_id,
            chapter_number=chapter_number,
        )

        await self.message_bus.publish(
            channel=f"agent.{recipient}",
            message=message.model_dump()
        )
        logger.debug(f"Message sent: {self.AGENT_NAME} -> {recipient}")

    async def broadcast(
        self,
        message_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> None:
        """广播消息"""
        from .message import AgentMessage

        message = AgentMessage(
            sender=self.AGENT_NAME,
            recipient="*",
            message_type=message_type,
            payload=payload,
            task_id=task_id,
        )

        await self.message_bus.publish(
            channel="agent.broadcast",
            message=message.model_dump()
        )

    # ========== 权限检查 ==========

    def _can_send_to(self, target: str) -> bool:
        """检查是否可以发送消息给目标 Agent。

        收敛后主流程不再使用 Agent 间消息传递（改为顺序调用 + 返回值驱动），
        PERMISSION_MATRIX 已移除。此方法保留作为兼容入口，默认放行；
        如未来重新引入消息总线协作，可在此恢复白名单校验。
        """
        return True

    def _register_capabilities(self) -> None:
        """注册 Agent 能力（子类可重写）"""
        pass

    async def _load_prompts(self) -> None:
        """加载提示词模板"""
        pass

    async def _load_config(self) -> None:
        """加载配置"""
        pass

    def get_capabilities(self) -> Dict[str, AgentCapability]:
        """获取 Agent 能力列表"""
        return self._capabilities.copy()
