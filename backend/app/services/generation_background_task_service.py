from __future__ import annotations

from typing import List, Optional

from .generation_analysis_task_service import GenerationAnalysisTaskService
from .generation_write_task_service import GenerationWriteTaskService


class GenerationBackgroundTaskService:
    """后台任务兼容门面，转发到分析/写入子服务。"""

    def __init__(
        self,
        *,
        analysis_tasks: Optional[GenerationAnalysisTaskService] = None,
        write_tasks: Optional[GenerationWriteTaskService] = None,
    ):
        self.analysis_tasks = analysis_tasks or GenerationAnalysisTaskService()
        self.write_tasks = write_tasks or GenerationWriteTaskService()

    async def run_chapter_post_processor(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
        user_id: int,
    ) -> None:
        await self.write_tasks.run_chapter_post_processor(
            project_id=project_id,
            chapter_number=chapter_number,
            content=content,
            user_id=user_id,
        )

    async def run_stage_b_analyses(
        self,
        *,
        version_id: int,
        analysis_snapshot: str,
        project_id: str,
        chapter_number: int,
        chapter_mission: Optional[dict],
        previous_summary: Optional[str],
        completed_chapters: List[dict],
        enable_reader_sim: bool,
        enable_anti_hallucination: bool,
        user_id: int,
        anti_hallucination_local_only: bool = False,
    ) -> None:
        await self.analysis_tasks.run_stage_b_analyses(
            version_id=version_id,
            analysis_snapshot=analysis_snapshot,
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_mission=chapter_mission,
            previous_summary=previous_summary,
            completed_chapters=completed_chapters,
            enable_reader_sim=enable_reader_sim,
            enable_anti_hallucination=enable_anti_hallucination,
            user_id=user_id,
            anti_hallucination_local_only=anti_hallucination_local_only,
        )

    async def run_six_dimension_review(
        self,
        *,
        version_id: int,
        project_id: str,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str,
        chapter_plan: Optional[str],
        previous_summary: Optional[str],
    ) -> None:
        await self.analysis_tasks.run_six_dimension_review(
            version_id=version_id,
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_content=chapter_content,
            chapter_plan=chapter_plan,
            previous_summary=previous_summary,
        )

    async def run_memory_update(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int,
    ) -> None:
        await self.write_tasks.run_memory_update(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_content=chapter_content,
            character_names=character_names,
            user_id=user_id,
        )

    async def run_state_update(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int,
    ) -> None:
        await self.write_tasks.run_state_update(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_content=chapter_content,
            character_names=character_names,
            user_id=user_id,
        )

    async def run_foreshadowing_extraction(
        self,
        *,
        project_id: str,
        chapter_id: int,
        chapter_number: int,
        chapter_content: str,
        user_id: int,
    ) -> None:
        await self.write_tasks.run_foreshadowing_extraction(
            project_id=project_id,
            chapter_id=chapter_id,
            chapter_number=chapter_number,
            chapter_content=chapter_content,
            user_id=user_id,
        )

    async def run_volume_retrospective(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
    ) -> None:
        await self.write_tasks.run_volume_retrospective(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
        )

    async def run_outline_revision(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        user_id: int,
    ) -> None:
        await self.write_tasks.run_outline_revision(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_content=chapter_content,
            user_id=user_id,
        )
