# AIMETA P=Agent系统入口|R=统一调度Agent系统|NR=协调各Agent完成写作任务|E=WritingAgentSystem|X=internal|A=系统入口|D=asyncio
"""Agent 系统入口"""
from __future__ import annotations

import inspect
import logging
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Type

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

    async def _emit_stage(
        self,
        stream_handler: Optional[Callable],
        stage: str,
        message: str,
    ) -> None:
        """推送阶段事件到前端"""
        if not stream_handler:
            return
        data = {"event": "stage", "stage": stage, "message": message}
        try:
            result = stream_handler(data)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            logger.debug("_emit_stage callback error (ignored): %s", e)

    async def execute_chapter_generation(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_input: Optional[str] = None,
        writing_notes: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        stream_handler: Optional[Callable] = None,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """执行章节生成（主入口）—— 顺序调度模式"""

        if not self._initialized:
            await self.initialize()

        # 为所有 Agent 设置流式事件推送
        for agent in self._agents.values():
            agent.set_stream_handler(stream_handler)

        await self._emit_stage(stream_handler, "agent:system:start", "三省六部系统启动")

        task_id = str(uuid.uuid4())
        effective_config = config or {}

        # 创建奏折档案
        archive = None
        if self.archive_service:
            try:
                archive = await self.archive_service.create_archive(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    user_command=user_input,
                    writing_notes=writing_notes,
                    preset=effective_config.get("preset"),
                )
                await self.archive_service.start_archive(archive.id)

                for agent in self._agents.values():
                    agent.set_archive_id(archive.id)

                logger.info(f"Created archive: {archive.imperial_edict_id}")
            except Exception as e:
                logger.warning(f"Failed to create archive: {e}")

        await self._emit_stage(stream_handler, "agent:system:archive", "奏折档案已创建")

        try:
            # ========== 阶段 1: 太子分拣 ==========
            taizi = self._agents.get("taizi")
            if not taizi:
                raise RuntimeError("TaiziAgent not initialized")

            taizi_context = AgentContext(
                task_id=task_id,
                project_id=project_id,
                chapter_number=chapter_number,
                user_input=user_input,
                mission={"writing_notes": writing_notes},
                config=effective_config,
            )
            taizi_result = await taizi.process(taizi_context)
            taizi_output = taizi_result.output or {}

            selected_skills = effective_config.get("selected_skills") or []
            skill_context = None
            skill_policies = []
            effective_writing_notes = writing_notes or ""
            if selected_skills:
                hubu = self._agents.get("hubu")
                if hubu:
                    hubu_context = AgentContext(
                        task_id=task_id,
                        project_id=project_id,
                        chapter_number=chapter_number,
                        user_input=user_input,
                        config=effective_config,
                        metadata={
                            "action": "build_skill_context",
                            "selected_skills": selected_skills,
                        },
                    )
                    hubu_result = await hubu.process(hubu_context)
                    if hubu_result.status == "completed":
                        skill_context = (hubu_result.output or {}).get("skill_context")
                        skill_policies = list((skill_context or {}).get("skill_policies") or [])
                        skill_prompt = (skill_context or {}).get("prompt_injection", "")
                        if skill_prompt:
                            effective_writing_notes = (
                                f"{effective_writing_notes}\n\n{skill_prompt}".strip()
                                if effective_writing_notes
                                else skill_prompt
                            )
                    else:
                        logger.warning("HubuAgent 构建技能上下文失败: %s", hubu_result.error)

            # ========== 阶段 2: 中书规划 ==========
            zhongshu = self._agents.get("zhongshu")
            if not zhongshu:
                raise RuntimeError("ZhongshuAgent not initialized")

            zhongshu_context = AgentContext(
                task_id=task_id,
                project_id=project_id,
                chapter_number=chapter_number,
                user_input=user_input,
                mission={"writing_notes": writing_notes},
                config=effective_config,
                metadata={
                    "user_id": user_id,
                    "parsed_command": taizi_output.get("parsed_command", {}),
                    "chapter_type": taizi_output.get("chapter_type", "普通章"),
                    "emotion_target": taizi_output.get("emotion_target", {}),
                    "writing_preferences": taizi_output.get("writing_preferences", {}),
                    "skill_policies": skill_policies,
                },
            )
            zhongshu_result = await zhongshu.process(zhongshu_context)
            zhongshu_output = zhongshu_result.output or {}

            # ========== 阶段 3: 尚书调度（由 system.py 代为协调） ==========
            await self._emit_stage(stream_handler, "agent:shangshu:start", "开始调度兵部生成章节")

            # ========== 阶段 4: 兵部生成 ==========
            bingbu = self._agents.get("bingbu")
            if not bingbu:
                raise RuntimeError("BingbuAgent not initialized")

            version_count = effective_config.get(
                "version_count", effective_config.get("versions", 3)
            )
            bingbu_context = AgentContext(
                task_id=task_id,
                project_id=project_id,
                chapter_number=chapter_number,
                user_input=user_input,
                config=effective_config,
                metadata={
                    "writing_prompt": zhongshu_output.get("writing_prompt", ""),
                    "version_count": version_count,
                    "user_id": user_id,
                    "flow_config": {
                        **effective_config,
                        "skip_bridge_archive": True,
                        "skill_policies": skill_policies,
                        "pre_collected_context": zhongshu_output.get("pre_collected_context"),
                    },
                    "writing_notes": effective_writing_notes,
                    "skill_context": skill_context,
                    "use_orchestrator": True,
                },
            )
            bingbu_result = await bingbu.process(bingbu_context)
            bingbu_output = bingbu_result.output or {}
            versions = bingbu_output.get("versions", [])

            await self._emit_stage(
                stream_handler, "agent:shangshu:done",
                f"收到 {len(versions)} 个版本，转交门下省审核",
            )

            # ========== 阶段 5: 门下审核 ==========
            menxia = self._agents.get("menxia")
            best_content = versions[0].get("content", "") if versions else ""

            if menxia and best_content:
                menxia_context = AgentContext(
                    task_id=task_id,
                    project_id=project_id,
                    chapter_number=chapter_number,
                    config=effective_config,
                    metadata={
                        "message_type": AgentMessageType.REVIEW_REQUEST.value,
                        "chapter": {"content": best_content, "versions": versions},
                    },
                )
                menxia_result = await menxia.process(menxia_context)
                review = (menxia_result.output or {}).get("review", {})
            else:
                review = {}

            # ========== 组装最终结果 ==========
            payload: Dict[str, Any] = {
                "versions": versions,
                "version_count": len(versions),
                "stages": bingbu_output.get("stages", {}),
                "best_version_index": 0,
                "review": review,
            }

            # 更新档案
            if archive and self.archive_service:
                try:
                    if versions:
                        word_count = sum(len(v.get("content", "")) for v in versions)
                        await self.archive_service.update_final_output(
                            archive.id,
                            selected_version=1,
                            word_count=word_count,
                        )
                        await self.archive_service.update_versions(
                            archive.id,
                            versions_data=versions,
                        )
                    await self.archive_service.complete_archive(archive.id)

                    payload["imperial_edict_id"] = archive.imperial_edict_id
                    payload["archive_id"] = archive.id

                except Exception as e:
                    logger.warning(f"Failed to update archive: {e}")

            await self._emit_stage(stream_handler, "agent:system:done", "三省六部系统执行完成")
            return payload

        except Exception as e:
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
