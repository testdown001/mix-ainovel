# AIMETA P=生成预热服务_并发任务调度|R=上下文预热_任务打包|NR=不含主流程编排|E=GenerationPrefetchService|X=internal|A=预热调度|D=asyncio|S=compute|RD=./README.ai
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GenerationPrefetchTasks:
    enhanced_context_task: Optional[asyncio.Task]
    memory_text_task: asyncio.Task
    rag_task: Optional[asyncio.Task]
    foreshadowing_task: asyncio.Task
    trajectory_task: Optional[asyncio.Task]
    user_style_task: asyncio.Task
    fingerprint_task: Optional[asyncio.Task]
    writer_prompt_task: asyncio.Task
    outline_revision_task: Optional[asyncio.Task] = None
    volume_replan_task: Optional[asyncio.Task] = None
    long_range_memory_task: Optional[asyncio.Task] = None


class GenerationPrefetchService:
    """统一调度章节生成前的并行预热任务。"""

    def __init__(
        self,
        *,
        async_task_service,
        enhanced_context_service,
        context_access_service,
        evidence_router,
        trajectory_analysis_service,
        user_style_service,
        fingerprint_service,
        writer_prompt_service,
        context_planner,
    ):
        self.async_task_service = async_task_service
        self.enhanced_context_service = enhanced_context_service
        self.context_access_service = context_access_service
        self.evidence_router = evidence_router
        self.trajectory_analysis_service = trajectory_analysis_service
        self.user_style_service = user_style_service
        self.fingerprint_service = fingerprint_service
        self.writer_prompt_service = writer_prompt_service
        self.context_planner = context_planner

    def schedule_prefetch_tasks(
        self,
        *,
        config: Any,
        project: Any,
        project_id: str,
        chapter_number: int,
        user_id: int,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        blueprint_dict: Dict[str, Any],
        context_plan: Any,
        history_context: Dict[str, Any],
        fast_rag_queries: Optional[list[str]],
        pre_rag_context: Optional[Dict[str, Any]],
    ) -> GenerationPrefetchTasks:
        need_enhanced = (
            config.enable_constitution
            or config.enable_persona
            or config.enable_foreshadowing
            or config.enable_faction
        )
        enhanced_context_task: Optional[asyncio.Task] = None
        if need_enhanced:
            enhanced_context_task = asyncio.create_task(
                self.async_task_service.run_with_timeout(
                    self.enhanced_context_service.prefetch_enhanced_context(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_outline=outline_summary,
                    ),
                    timeout_sec=30,
                    task_name="enhanced_flow",
                    fallback={},
                )
            )

        memory_text_task = asyncio.create_task(
            self.async_task_service.run_with_timeout(
                self.context_access_service.prefetch_project_memory_text(project_id),
                timeout_sec=10,
                task_name="project_memory",
            )
        )

        rag_task: Optional[asyncio.Task] = None
        if config.enable_rag and config.rag_mode != "two_stage" and not pre_rag_context:
            rag_character_names = [
                item.get("name", "")
                for item in (blueprint_dict.get("characters", []) if blueprint_dict else [])
                if item.get("name")
            ][:6]
            rag_queries = self.context_planner.build_retrieval_queries(
                plan=context_plan,
                outline_title=outline_title,
                outline_summary=outline_summary,
                writing_notes=writing_notes,
                character_names=rag_character_names,
                story_skeleton=history_context.get("story_skeleton"),
                fast_rag_queries=fast_rag_queries,
            )
            rag_task = asyncio.create_task(
                self.async_task_service.run_with_timeout(
                    self.evidence_router.prefetch_local_plot(
                        plan=context_plan,
                        project_id=project_id,
                        user_id=user_id,
                        queries=rag_queries or [outline_title or outline_summary],
                        retrieval_mode=config.rag_retrieval_mode,
                    ),
                    timeout_sec=20,
                    task_name="rag_retrieval",
                    fallback={},
                )
            )

        foreshadowing_task = asyncio.create_task(
            self.async_task_service.run_with_timeout(
                self.evidence_router.prefetch_symbolic_foreshadowing(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    query_text=outline_summary or outline_title,
                ),
                timeout_sec=15,
                task_name="foreshadowing",
            )
        )

        trajectory_task: Optional[asyncio.Task] = None
        if config.enable_trajectory_analysis and chapter_number >= 4:
            trajectory_task = asyncio.create_task(
                self.async_task_service.run_with_timeout(
                    self.trajectory_analysis_service.prefetch_trajectory_context(
                        project_id=project_id,
                        project=project,
                        chapter_number=chapter_number,
                    ),
                    timeout_sec=5,
                    task_name="trajectory_analysis",
                )
            )

        outline_revision_task: Optional[asyncio.Task] = None
        if getattr(config, "enable_outline_revision", False):
            from .outline_revision_service import OutlineRevisionService

            outline_revision_task = asyncio.create_task(
                self.async_task_service.run_with_timeout(
                    OutlineRevisionService().build_revision_brief(
                        project_id=project_id,
                        chapter_number=chapter_number,
                    ),
                    timeout_sec=5,
                    task_name="outline_revision",
                )
            )

        volume_replan_task: Optional[asyncio.Task] = None
        if getattr(config, "enable_volume_retrospective", False):
            from .volume_retrospective_service import VolumeRetrospectiveService

            volume_replan_task = asyncio.create_task(
                self.async_task_service.run_with_timeout(
                    VolumeRetrospectiveService().build_replan_brief(
                        project_id=project_id,
                        chapter_number=chapter_number,
                    ),
                    timeout_sec=5,
                    task_name="volume_replan",
                )
            )

        # 卷级/书级分层长程记忆（DB 直查，非向量检索）：fast 路径保持轻量不预取
        long_range_memory_task: Optional[asyncio.Task] = None
        if not config.enable_fast_path:
            long_range_memory_task = asyncio.create_task(
                self.async_task_service.run_with_timeout(
                    self._prefetch_long_range_memory(
                        project_id=project_id,
                        chapter_number=chapter_number,
                    ),
                    timeout_sec=5,
                    task_name="long_range_memory",
                )
            )

        user_style_task = asyncio.create_task(
            self.async_task_service.run_with_timeout(
                self.user_style_service.prefetch_user_style(user_id),
                timeout_sec=10,
                task_name="user_style",
                fallback=(None, None),
            )
        )

        fingerprint_task: Optional[asyncio.Task] = None
        if config.enable_fingerprint:
            fingerprint_task = asyncio.create_task(
                self.async_task_service.run_with_timeout(
                    self.fingerprint_service.prefetch_fingerprint_context(
                        project_id=project_id,
                        project=project,
                        chapter_number=chapter_number,
                    ),
                    timeout_sec=10,
                    task_name="fingerprint",
                )
            )

        writer_prompt_task = asyncio.create_task(
            self.async_task_service.run_with_timeout(
                self.writer_prompt_service.prefetch_writer_prompt(
                    enable_fast_path=config.enable_fast_path,
                ),
                timeout_sec=5,
                task_name="writer_prompt",
            )
        )

        return GenerationPrefetchTasks(
            enhanced_context_task=enhanced_context_task,
            memory_text_task=memory_text_task,
            rag_task=rag_task,
            foreshadowing_task=foreshadowing_task,
            trajectory_task=trajectory_task,
            user_style_task=user_style_task,
            fingerprint_task=fingerprint_task,
            writer_prompt_task=writer_prompt_task,
            outline_revision_task=outline_revision_task,
            volume_replan_task=volume_replan_task,
            long_range_memory_task=long_range_memory_task,
        )

    async def _prefetch_long_range_memory(
        self,
        *,
        project_id: str,
        chapter_number: int,
        session: Any = None,
    ) -> Optional[Dict[str, Optional[str]]]:
        """DB 直查卷级/书级摘要，转正为 [卷级前情]/[全书脉络] 独立段的数据源。

        返回 {"volume_summaries_text", "book_summary_text"}；数据缺失时对应值为 None，
        查询失败整体返回 None——全程降级，绝不影响生成主流程。
        """
        try:
            async def _run(sess: Any) -> Dict[str, Optional[str]]:
                from .book_summary_service import BookSummaryService
                from .volume_summary_service import VolumeSummaryService

                # 只读摘要，不触发 LLM 调用，llm_service 传 None 即可
                volumes = await VolumeSummaryService(sess, None).get_relevant_volume_summaries(
                    project_id, chapter_number, max_volumes=3
                )
                book_summary = await BookSummaryService(sess, None).get_book_summary(project_id)
                return {
                    "volume_summaries_text": self._format_volume_summaries(volumes),
                    "book_summary_text": (book_summary or "").strip() or None,
                }

            if session is not None:
                return await _run(session)

            from ..db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as own_session:
                return await _run(own_session)
        except Exception as exc:
            logger.warning("卷/书级摘要预取失败（不影响生成）: %s", exc)
            return None

    @staticmethod
    def _format_volume_summaries(volumes: Optional[List[Dict[str, Any]]]) -> Optional[str]:
        """把最近数卷的卷级摘要拼装为 prompt 段文本，全部为空则返回 None。"""
        parts: List[str] = []
        for vol in volumes or []:
            summary = str(vol.get("summary") or "").strip()
            if not summary:
                continue
            title = str(vol.get("title") or f"第{vol.get('volume_number')}卷").strip()
            parts.append(f"### {title}\n{summary}")
        return "\n\n".join(parts) if parts else None
