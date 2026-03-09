# AIMETA P=混合执行器|R=新旧系统共存|NR=支持Agent和传统流水线切换|E=HybridExecutor|X=internal|A=系统入口|D=asyncio
"""混合执行器 - 新旧系统共存"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .system import WritingAgentSystem

logger = logging.getLogger(__name__)


class HybridExecutor:
    """混合执行器：新旧系统共存"""

    def __init__(self, session: AsyncSession, user_id: Optional[int] = None):
        self.session = session
        self.user_id = user_id
        self.agent_system: Optional[WritingAgentSystem] = None
        self.legacy_orchestrator = None
        self._agent_system_enabled = False

        # 奏折服务
        self._archive_service = None

    def _get_archive_service(self):
        """获取档案服务"""
        if self._archive_service is None:
            from ..services.writing_archive_service import WritingArchiveService
            self._archive_service = WritingArchiveService(self.session)
        return self._archive_service

    async def initialize_agent_system(self) -> None:
        """初始化 Agent 系统"""
        if not self._agent_system_enabled:
            return

        try:
            archive_service = self._get_archive_service()
            self.agent_system = WritingAgentSystem(self.session, archive_service=archive_service)
            await self.agent_system.initialize()
            logger.info("Agent system initialized with archive service")
        except Exception as e:
            logger.error(f"Failed to initialize agent system: {e}")
            self._agent_system_enabled = False

    async def generate_chapter(
        self,
        *,
        use_agent: bool = False,
        project_id: str,
        chapter_number: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
        stream_handler: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """选择使用 Agent 系统或传统流水线"""

        if use_agent and self._agent_system_enabled and self.agent_system:
            return await self._use_agent_system(
                project_id=project_id,
                chapter_number=chapter_number,
                writing_notes=writing_notes,
                flow_config=flow_config,
                stream_handler=stream_handler,
            )
        else:
            return await self._use_legacy_pipeline(
                project_id=project_id,
                chapter_number=chapter_number,
                writing_notes=writing_notes,
                flow_config=flow_config,
                stream_handler=stream_handler,
            )

    async def _use_agent_system(
        self,
        project_id: str,
        chapter_number: int,
        writing_notes: Optional[str],
        flow_config: Optional[Dict[str, Any]],
        stream_handler: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """使用 Agent 系统生成"""
        config = flow_config or {}
        # 传递完整 flow_config，补充 version_count 便于下游读取
        agent_config = dict(config)
        agent_config.setdefault("version_count", config.get("versions", 3))

        result = await self.agent_system.execute_chapter_generation(
            project_id=project_id,
            chapter_number=chapter_number,
            user_input=writing_notes,
            writing_notes=writing_notes,
            config=agent_config,
            stream_handler=stream_handler,
            user_id=self.user_id or 0,
        )

        # 适配返回格式为 PipelineOrchestrator 格式
        variants = []
        versions = result.get("versions", [])

        for idx, v in enumerate(versions):
            variants.append({
                "index": idx,
                "version_id": idx + 1,
                "content": v.get("content", ""),
                "metadata": {
                    "version_id": v.get("version_id"),
                    "word_count": v.get("word_count", 0),
                },
            })

        if not variants:
            variants = [{
                "index": 0,
                "version_id": 1,
                "content": result.get("content", ""),
                "metadata": {},
            }]

        return {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "preset": "agent",
            "best_version_index": 0,
            "variants": variants,
            "review_summaries": result.get("review_summaries", {}),
            "debug_metadata": {
                "version_count": len(variants),
                "mode": "agent_system",
                "agent_result": result,
            },
            # 奏折信息
            "imperial_edict_id": result.get("imperial_edict_id"),
            "archive_id": result.get("archive_id"),
        }

    async def _use_legacy_pipeline(
        self,
        project_id: str,
        chapter_number: int,
        writing_notes: Optional[str],
        flow_config: Optional[Dict[str, Any]],
        stream_handler: Optional[Any],
    ) -> Dict[str, Any]:
        """使用传统流水线"""
        if not self.legacy_orchestrator:
            from ..services.pipeline_orchestrator import PipelineOrchestrator

            self.legacy_orchestrator = PipelineOrchestrator(self.session)

        return await self.legacy_orchestrator.generate_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=self.user_id,
            writing_notes=writing_notes,
            flow_config=flow_config,
            stream_handler=stream_handler,
        )

    async def shutdown(self) -> None:
        """关闭系统"""
        if self.agent_system:
            await self.agent_system.shutdown()

    def enable_agent_system(self) -> None:
        """启用 Agent 系统"""
        self._agent_system_enabled = True

    def disable_agent_system(self) -> None:
        """禁用 Agent 系统"""
        self._agent_system_enabled = False
