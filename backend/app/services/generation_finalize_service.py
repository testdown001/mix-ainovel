# AIMETA P=生成收尾服务_后台派发与响应组装|R=后台任务派发_归档_响应收尾|NR=不含主生成逻辑|E=GenerationFinalizeService|X=internal|A=收尾阶段|D=asyncio|S=compute|RD=./README.ai
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..core.constants import StageStatus, WritingStage
from .writer_progress_service import progress_service

logger = logging.getLogger(__name__)


class GenerationFinalizeService:
    """统一封装章节生成后的后台派发、归档与响应收尾。"""

    def __init__(
        self,
        *,
        generation_background_task_service,
        narrative_verifier,
        generation_result_service,
        generation_policy_service,
    ):
        self.generation_background_task_service = generation_background_task_service
        self.narrative_verifier = narrative_verifier
        self.generation_result_service = generation_result_service
        self.generation_policy_service = generation_policy_service

    @staticmethod
    def _track_task(task_registry: set, task: asyncio.Task) -> None:
        task_registry.add(task)

        def _on_done(t: asyncio.Task) -> None:
            task_registry.discard(t)
            if not t.cancelled():
                exc = t.exception()
                if exc is not None:
                    logger.exception("后台任务 [%s] 异常终止", t.get_name(), exc_info=exc)

        task.add_done_callback(_on_done)

    def schedule_followups(
        self,
        *,
        task_registry: set,
        versions_models: List[Any],
        best_version_index: int,
        project_id: str,
        chapter: Any,
        chapter_number: int,
        best_content: str,
        introduced_characters: List[str],
        user_id: int,
        enable_memory: bool,
        enable_state_tracking: bool = False,
        enable_outline_revision: bool = False,
        enable_volume_retrospective: bool = False,
        enable_character_significance: bool = False,
        stage_b_params: Optional[Dict[str, Any]] = None,
        six_dimension_payload: Optional[Dict[str, Any]] = None,
        run_post_processor: bool = False,
    ) -> None:
        if six_dimension_payload and versions_models:
            best_version_id = versions_models[best_version_index].id
            task = asyncio.create_task(
                self.generation_background_task_service.run_six_dimension_review(
                    version_id=best_version_id,
                    **six_dimension_payload,
                )
            )
            self._track_task(task_registry, task)

        if stage_b_params and 0 <= best_version_index < len(versions_models):
            stage_b_version_id = versions_models[best_version_index].id
            task = asyncio.create_task(
                self.generation_background_task_service.run_stage_b_analyses(
                    version_id=stage_b_version_id,
                    **stage_b_params,
                )
            )
            self._track_task(task_registry, task)

        if enable_memory:
            task = asyncio.create_task(
                self.generation_background_task_service.run_memory_update(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_content=best_content,
                    character_names=introduced_characters,
                    user_id=user_id,
                )
            )
            self._track_task(task_registry, task)
        elif enable_state_tracking:
            # standard 档轻量路径：仅状态类抽取落库（CharacterState/TimelineEvent），不碰 mem0
            task = asyncio.create_task(
                self.generation_background_task_service.run_state_update(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_content=best_content,
                    character_names=introduced_characters,
                    user_id=user_id,
                )
            )
            self._track_task(task_registry, task)

        task = asyncio.create_task(
            self.generation_background_task_service.run_foreshadowing_extraction(
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_number=chapter_number,
                chapter_content=best_content,
                user_id=user_id,
            )
        )
        self._track_task(task_registry, task)

        if enable_outline_revision:
            task = asyncio.create_task(
                self.generation_background_task_service.run_outline_revision(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_content=best_content,
                    user_id=user_id,
                )
            )
            self._track_task(task_registry, task)

        # 人物意义等待实际采用/定稿后再提取，不能从推荐但尚未选中的版本学习。
        # 每个版本已经保存 character_significance_enabled，后处理沿用该选择。

        if enable_volume_retrospective:
            task = asyncio.create_task(
                self.generation_background_task_service.run_volume_retrospective(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    user_id=user_id,
                )
            )
            self._track_task(task_registry, task)

        if run_post_processor:
            task = asyncio.create_task(
                self.generation_background_task_service.run_chapter_post_processor(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    content=best_content,
                    user_id=user_id,
                )
            )
            self._track_task(task_registry, task)

    async def complete_progress(
        self,
        *,
        project_id: str,
        chapter_number: int,
        message: str,
    ) -> None:
        await progress_service.update_stage(
            project_id,
            chapter_number,
            WritingStage.MAIN_WRITING,
            StageStatus.COMPLETED,
            progress=100,
            message=message,
        )
        await progress_service.complete(project_id, chapter_number, success=True)

    @staticmethod
    def build_variants(
        *,
        versions_models: List[Any],
        versions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        variants: List[Dict[str, Any]] = []
        for idx, version_model in enumerate(versions_models):
            variants.append(
                {
                    "index": idx,
                    "version_id": version_model.id,
                    "content": versions[idx].get("content", ""),
                    "metadata": versions[idx].get("metadata"),
                }
            )
        return variants

    @staticmethod
    def build_single_variant(
        *,
        version_model: Any,
        version: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return [
            {
                "index": 0,
                "version_id": version_model.id,
                "content": version.get("content", ""),
                "metadata": version.get("metadata"),
            }
        ]

    async def complete_archive(
        self,
        *,
        archive_service: Any,
        archive_id: Optional[int],
        variants: List[Dict[str, Any]],
        versions_models: List[Any],
        best_version_index: int,
        version_count: int,
        gatekeeper_score: Optional[float],
        warning_label: str,
        performance_metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not archive_id:
            return
        try:
            final_version_id = None
            if variants and best_version_index < len(variants):
                final_version_id = variants[best_version_index].get("version_id")
            elif versions_models and best_version_index < len(versions_models):
                final_version_id = versions_models[best_version_index].id

            archive_kwargs = {
                "final_version_id": final_version_id,
                "version_count": version_count,
                "gatekeeper_score": gatekeeper_score,
            }
            if performance_metrics is not None:
                archive_kwargs["performance_metrics"] = performance_metrics
            await archive_service.complete_archive(archive_id, **archive_kwargs)
        except Exception as exc:
            logger.warning("%s: %s", warning_label, exc)

    async def finalize_response(
        self,
        *,
        plan: Any,
        chapter_text: str,
        review_summaries: Dict[str, Any],
        retrieval_evidence_summary: Dict[str, Any],
        versions: List[Dict[str, Any]],
        variants: List[Dict[str, Any]],
        best_version_index: int,
        telemetry: Any,
        emit_completed: Callable[[], Awaitable[None]],
        project_id: str,
        chapter_number: int,
        preset: str,
        mode: Optional[str],
        config: Any,
        rag_stats: Optional[Dict[str, Any]],
        context_plan_payload: Dict[str, Any],
        prompt_compile_summary: Dict[str, Any],
        stage_timings_ms: Dict[str, int],
        strategy_warnings: List[str],
        skill_usage_feedback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        verification_report = self.narrative_verifier.verify(
            plan=plan,
            chapter_text=chapter_text,
            review_summaries=review_summaries,
            evidence_summary=retrieval_evidence_summary,
        )
        self.generation_result_service.attach_verification_report(
            verification_report=verification_report,
            versions=versions,
            variants=variants,
            best_version_index=best_version_index,
        )
        if skill_usage_feedback:
            try:
                await skill_usage_feedback(verification_report)
            except Exception as exc:
                # 效果指标是旁路能力，不能让正文生成因埋点失败而失败。
                logger.warning("技能质量回执写入失败: %s", exc)
        await telemetry.emit_verification_report(verification_report)
        await emit_completed()

        debug_metadata = self.generation_result_service.build_debug_metadata(
            version_count=len(variants),
            mode=mode,
            stage_flags=self.generation_policy_service.build_stage_flags(config),
            rag_stats=rag_stats,
            context_plan=context_plan_payload,
            retrieval_evidence_summary=retrieval_evidence_summary,
            prompt_compile_summary=prompt_compile_summary,
            verification_report=verification_report,
            stage_timings_ms=stage_timings_ms,
            llm_metrics=telemetry.llm_metrics,
            strategy_warnings=strategy_warnings,
        )
        return self.generation_result_service.build_response_payload(
            project_id=project_id,
            chapter_number=chapter_number,
            preset=preset,
            best_version_index=best_version_index,
            variants=variants,
            review_summaries=review_summaries,
            debug_metadata=debug_metadata,
        )
