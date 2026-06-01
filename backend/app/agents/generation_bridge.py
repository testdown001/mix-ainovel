"""Agent generation enhancement module.

This module provides deep integration between the Agent system and the
traditional pipeline, allowing agents to reuse PipelineOrchestrator's
complete generation capabilities while maintaining agent architecture
flexibility.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.pipeline_orchestrator import PipelineOrchestrator
from ..services.writer_progress_service import progress_service, WritingStage, StageStatus
from ..services.writing_archive_service import WritingArchiveService

logger = logging.getLogger(__name__)


class AgentGenerationBridge:
    """Agent Generation Bridge - enables calling Pipeline generation capabilities within Agent architecture"""

    def __init__(self, session: AsyncSession, user_id: int):
        self.session = session
        self.user_id = user_id

    async def generate_with_orchestrator(
        self,
        *,
        project_id: str,
        chapter_number: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
        version_count: int = 3,
    ) -> Dict[str, Any]:
        """Generate chapter using PipelineOrchestrator"""
        # Create archive record (skip if called from Agent system to avoid duplicate)
        archive_id = None
        if not (flow_config or {}).get("skip_bridge_archive"):
            archive_service = WritingArchiveService(self.session)
            try:
                archive = await archive_service.create_archive(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    user_command=writing_notes,
                    writing_notes=writing_notes,
                    preset=flow_config.get("preset") if flow_config else None,
                )
                archive_id = archive.id
            except Exception as e:
                logger.warning(f"Archive creation failed: {e}")
                await self.session.rollback()

        # Use PipelineOrchestrator for generation
        orchestrator = PipelineOrchestrator(self.session)
        
        # Collect streaming events
        collected_events = []
        
        def stream_handler(event: Dict[str, Any]) -> None:
            """Collect streaming events for later analysis"""
            collected_events.append(event)
            logger.debug(f"Stage: {event.get('event')}, data: {event}")

        try:
            result = await orchestrator.generate_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=self.user_id,
                writing_notes=writing_notes,
                flow_config=flow_config,
                stream_handler=stream_handler,
            )

            # Update archive
            if archive_id:
                archive_service = WritingArchiveService(self.session)
                await archive_service.complete_archive(archive_id)

            return {
                "status": "success",
                "versions": result.get("variants", []),
                "best_version": result.get("best_version_index", 0),
                "stages": self._extract_stages(collected_events),
                "metadata": {
                    "generation_time_ms": result.get("total_time_ms", 0),
                    "version_count": result.get("debug_metadata", {}).get("version_count", version_count),
                }
            }

        except Exception as e:
            logger.error(f"Agent generation failed: {e}")
            
            if archive_id:
                await archive_service.fail_archive(archive_id, str(e))
            
            raise

    def _extract_stages(self, events: list) -> Dict[str, Any]:
        """Extract stage information from event stream"""
        stages = {}
        for event in events:
            if event.get("event") == "stage":
                stage_name = event.get("stage", "unknown")
                stages[stage_name] = {
                    "message": event.get("message", ""),
                    "progress": event.get("progress", 0),
                }
        return stages
