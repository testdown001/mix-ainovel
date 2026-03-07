# AIMETA P=Agent系统入口|R=统一调度Agent系统|NR=协调各Agent完成写作任务|E=WritingAgentSystem|X=internal|A=系统入口|D=asyncio
"""Agent 系统入口"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseAgent
from .message import AgentContext, AgentMessageType
from .message_bus import AgentMessageBus

if TYPE_CHECKING:
    from .taizi_agent import TaiziAgent
    from .zhongshu_agent import ZhongshuAgent
    from .shangshu_agent import ShangshuAgent
    from .bingbu_agent import BingbuAgent
    from .hubu_agent import HubuAgent
    from .libu_agent import LibuAgent
    from .menxia_agent import MenxiaAgent

logger = logging.getLogger(__name__)


class WritingAgentSystem:
    """Agent 系统入口"""

    AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}

    PERMISSION_MATRIX = {
        "taizi": ["zhongshu"],
        "zhongshu": ["taizi", "menxia", "shangshu"],
        "menxia": ["taizi", "zhongshu"],
        "shangshu": ["taizi", "zhongshu", "hubu", "libu", "bingbu"],
        "hubu": ["shangshu"],
        "libu": ["shangshu"],
        "bingbu": ["shangshu"],
    }

    # Agent 阶段名称映射
    STAGE_NAMES = {
        "taizi": "太子分拣",
        "zhongshu": "中书规划",
        "shangshu": "尚书汇总",
        "bingbu": "兵部生成",
        "hubu": "户部技能",
        "libu": "吏部校验",
        "menxia": "门下审核",
    }

    def __init__(self, session: AsyncSession, archive_service=None):
        self.session = session
        self.archive_service = archive_service
        self.message_bus = AgentMessageBus()
        self._agents: Dict[str, BaseAgent] = {}
        self._initialized = False

    @classmethod
    def register_agent(cls, name: str, agent_class: Type[BaseAgent]) -> None:
        """注册 Agent"""
        cls.AGENT_REGISTRY[name] = agent_class

    async def initialize(self) -> None:
        """初始化系统"""
        if self._initialized:
            return

        await self.message_bus.initialize()

        # 注册所有 Agent
        self._register_agents()

        # 创建所有 Agent 实例
        for name, agent_class in self.AGENT_REGISTRY.items():
            agent = agent_class(
                agent_id=f"{name}_{uuid.uuid4().hex[:8]}",
                session=self.session
            )
            agent.message_bus = self.message_bus

            # 设置档案服务
            if self.archive_service:
                agent.set_archive_service(self.archive_service)

            await agent.initialize()
            self._agents[name] = agent

        self._initialized = True

    def _register_agents(self) -> None:
        """注册所有 Agent 类"""
        if not self.AGENT_REGISTRY:
            from .taizi_agent import TaiziAgent
            from .zhongshu_agent import ZhongshuAgent
            from .shangshu_agent import ShangshuAgent
            from .bingbu_agent import BingbuAgent
            from .hubu_agent import HubuAgent
            from .libu_agent import LibuAgent
            from .menxia_agent import MenxiaAgent

            self.register_agent("taizi", TaiziAgent)
            self.register_agent("zhongshu", ZhongshuAgent)
            self.register_agent("shangshu", ShangshuAgent)
            self.register_agent("bingbu", BingbuAgent)
            self.register_agent("hubu", HubuAgent)
            self.register_agent("libu", LibuAgent)
            self.register_agent("menxia", MenxiaAgent)

    async def shutdown(self) -> None:
        """关闭系统"""
        for agent in self._agents.values():
            await agent.cleanup()
        await self.message_bus.shutdown()
        self._initialized = False

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取 Agent 实例"""
        return self._agents.get(name)

    async def execute_chapter_generation(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_input: Optional[str] = None,
        writing_notes: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行章节生成（主入口）"""

        if not self._initialized:
            await self.initialize()

        # 创建任务
        task_id = str(uuid.uuid4())

        # 创建奏折档案
        archive = None
        if self.archive_service:
            try:
                archive = await self.archive_service.create_archive(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    user_command=user_input,
                    writing_notes=writing_notes,
                    preset=config.get("preset") if config else None,
                )
                await self.archive_service.start_archive(archive.id)

                # 为所有 Agent 设置档案 ID
                for agent in self._agents.values():
                    agent.set_archive_id(archive.id)

                logger.info(f"Created archive: {archive.imperial_edict_id}")
            except Exception as e:
                logger.warning(f"Failed to create archive: {e}")

        # 注册任务结果回调
        result_holder: Dict[str, Any] = {}

        async def collect_result(message: Dict[str, Any]) -> None:
            msg_type = message.get("message_type")
            if msg_type == AgentMessageType.TASK_COMPLETED.value:
                result_holder["result"] = message.get("payload")
            elif msg_type == AgentMessageType.TASK_FAILED.value:
                result_holder["error"] = message.get("payload")

        await self.message_bus.subscribe("task_collector", collect_result)
        await self.message_bus.subscribe_broadcast(collect_result)

        # 启动太子省
        taizi = self._agents.get("taizi")
        if not taizi:
            raise RuntimeError("TaiziAgent not initialized")

        context = AgentContext(
            task_id=task_id,
            project_id=project_id,
            chapter_number=chapter_number,
            user_input=user_input,
            mission={"writing_notes": writing_notes},
            config=config or {},
        )

        try:
            result = await taizi.process(context)

            # 等待最终结果
            final_result = await self.message_bus.wait_for_message(
                task_id=task_id,
                timeout=600
            )

            if final_result:
                payload = final_result.get("payload", {})
            elif "error" in result_holder:
                payload = {}
            else:
                payload = result_holder.get("result", {"status": "completed"})

            # 更新档案
            if archive and self.archive_service:
                try:
                    versions = payload.get("versions", [])
                    if versions:
                        word_count = sum(len(v.get("content", "")) for v in versions)
                        await self.archive_service.update_final_output(
                            archive.id,
                            selected_version=payload.get("best_version_index", 0) + 1,
                            word_count=word_count,
                        )
                        await self.archive_service.update_versions(
                            archive.id,
                            versions_data=versions,
                        )
                    await self.archive_service.complete_archive(archive.id)

                    # 返回结果中添加奏折ID
                    payload["imperial_edict_id"] = archive.imperial_edict_id
                    payload["archive_id"] = archive.id

                except Exception as e:
                    logger.warning(f"Failed to update archive: {e}")

            return payload

        except Exception as e:
            # 标记档案失败
            if archive and self.archive_service:
                try:
                    await self.archive_service.fail_archive(archive.id, str(e))
                except Exception:
                    pass
            raise

    @property
    def agents(self) -> Dict[str, BaseAgent]:
        """获取所有 Agent"""
        return self._agents.copy()
