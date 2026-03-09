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


class AgentConsistencyChecker:
    """Agent Consistency Checker - provides pre-generation consistency checks"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def pre_generate_check(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_mission: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Pre-generation consistency check"""
        from ..services.consistency_service import ConsistencyService

        consistency_service = ConsistencyService(self.session)

        # Extract key info from mission
        pov_character = chapter_mission.get("pov_character", {})
        target_realm = chapter_mission.get("target_realm")
        chapter_outline = chapter_mission.get("chapter_outline", "")

        warnings = []

        # Check 1: Realm jump reasonableness
        if target_realm:
            realm_jump = await self._check_realm_jump(
                project_id, pov_character, target_realm
            )
            if realm_jump:
                warnings.append({
                    "type": "realm_jump",
                    "severity": "warning",
                    "message": realm_jump,
                })

        # Check 2: Timeline consistency
        timeline_issues = await self._check_timeline(project_id, chapter_number)
        if timeline_issues:
            warnings.extend(timeline_issues)

        # Check 3: Character status
        character_issues = await self._check_character_status(
            project_id, chapter_number, chapter_outline
        )
        if character_issues:
            warnings.extend(character_issues)

        return {
            "has_warnings": len(warnings) > 0,
            "warnings": warnings,
            "can_proceed": True,
        }

    async def _check_realm_jump(
        self,
        project_id: str,
        pov_character: Dict[str, Any],
        target_realm: str,
    ) -> Optional[str]:
        """Check if realm jump is too large"""
        if not pov_character:
            return None

        current_realm = pov_character.get("realm", "")
        if not current_realm:
            return None

        # Simple realm ordering
        realm_order = {
            "练气": 1, "筑基": 2, "金丹": 3, "元婴": 4,
            "化神": 5, "炼虚": 6, "合体": 7, "大乘": 8,
        }

        current_level = realm_order.get(current_realm, 0)
        target_level = realm_order.get(target_realm, 0)

        if current_level > 0 and target_level > 0:
            jump = target_level - current_level
            if jump > 2:
                return f"Large realm jump: from {current_realm} to {target_realm}"

        return None

    async def _check_timeline(
        self,
        project_id: str,
        chapter_number: int,
    ) -> list:
        """Check timeline issues"""
        return []

    async def _check_character_status(
        self,
        project_id: str,
        chapter_number: int,
        chapter_outline: str,
    ) -> list:
        """Check character status issues"""
        return []


class AgentReviewAdapter:
    """Agent Review Adapter - adapts Pipeline review capabilities for Agent system"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def review_versions(
        self,
        *,
        versions: list,
        project_id: str,
        chapter_number: int,
        chapter_mission: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Review multiple versions and return best selection"""
        from ..services.ai_review_service import AIReviewService
        from ..services.prompt_service import PromptService
        from ..services.llm_service import LLMService

        llm_service = LLMService(self.session)
        prompt_service = PromptService(self.session)
        review_service = AIReviewService(llm_service, prompt_service)

        contents = [v.get("content", "") for v in versions]

        try:
            result = await review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=0,
            )

            return {
                "best_index": result.best_version_index,
                "scores": result.scores,
                "evaluation": result.overall_evaluation,
                "flaws": result.critical_flaws,
                "suggestions": result.refinement_suggestions,
            }
        except Exception as e:
            logger.error(f"Agent review failed: {e}")
            return {
                "best_index": 0,
                "error": str(e),
            }


class AgentForeshadowingIntegrator:
    """Agent Foreshadowing Integrator - provides foreshadowing guidance and completion checks"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_foreshadowing_guide(
        self,
        *,
        project_id: str,
        chapter_number: int,
    ) -> Dict[str, Any]:
        """Get foreshadowing guidance for current chapter"""
        from ..services.foreshadowing_service import ForeshadowingService

        service = ForeshadowingService(self.session)

        # Get unresolved foreshadowings
        unresolved = await service.get_unresolved_foreshadowings(
            project_id=project_id,
            before_chapter=chapter_number,
        )

        # Sort by urgency
        should_resolve = [
            {
                "id": f.id,
                "content": f.content,
                "keywords": f.keywords,
                "chapter_number": f.chapter_number,
                "urgency": "high" if chapter_number - f.chapter_number >= 3 else "normal",
            }
            for f in unresolved[:5]
        ]

        should_plant = []

        return {
            "should_resolve": should_resolve,
            "should_plant": should_plant,
            "total_unresolved": len(unresolved),
        }

    async def check_resolution(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
    ) -> Dict[str, Any]:
        """Check if chapter covers expected foreshadowing"""
        from ..services.foreshadowing_service import ForeshadowingService

        service = ForeshadowingService(self.session)

        unresolved = await service.get_unresolved_foreshadowings(
            project_id=project_id,
            before_chapter=chapter_number,
        )

        resolved = []
        still_pending = []

        for foreshadowing in unresolved:
            if any(kw in content for kw in foreshadowing.keywords):
                resolved.append(foreshadowing.id)
                await service.resolve_foreshadowing(
                    foreshadowing.id,
                    resolution_chapter=chapter_number,
                    resolution_method="auto_detected",
                )
            else:
                still_pending.append(foreshadowing.id)

        return {
            "resolved_count": len(resolved),
            "pending_count": len(still_pending),
            "resolved_ids": resolved,
            "pending_ids": still_pending,
            "completion_rate": len(resolved) / max(len(unresolved), 1),
        }
