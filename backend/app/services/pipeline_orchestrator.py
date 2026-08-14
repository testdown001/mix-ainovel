# AIMETA P=写作流水线编排_统一生成入口|R=上下文汇聚_生成_审查_优化|NR=不含API路由|E=PipelineOrchestrator|X=internal|A=编排器|D=fastapi,sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.constants import StageStatus, WritingStage
from ..db.session import AsyncSessionLocal
from ..models.novel import Chapter, ChapterVersion
from ..services.chapter_guardrails import default_guardrails
from ..services.llm_service import LLMService
from ..services.cache_service import CacheService
from ..services.novel_service import NovelService
from ..services.preview_generation_service import PreviewGenerationService
from ..services.reference_novel_library_service import ReferenceNovelLibraryService
from ..services.prompt_service import PromptService
from ..services.writer_context_builder import default_context_builder
from ..services.chapter_post_processor import ChapterPostProcessor
from ..services.context_planner_service import ContextPlan, ContextPlannerService
from ..services.evidence_router_service import EvidenceRouterService
from ..services.history_context_service import HistoryContextService
from ..services.generation_result_service import GenerationResultService
from ..services.generation_telemetry_service import GenerationTelemetryService
from ..services.generation_policy_service import GenerationPolicyService
from ..services.generation_background_task_service import GenerationBackgroundTaskService
from ..services.context_access_service import ContextAccessService
from ..services.enhanced_context_service import EnhancedContextService
from ..services.generation_context_resolution_service import GenerationContextResolutionService
from ..services.generation_evidence_stage_service import GenerationEvidenceStageService
from ..services.generation_prompt_context_service import GenerationPromptContextService
from ..services.generation_prompt_stage_service import GenerationPromptStageService
from ..services.generation_finalize_service import GenerationFinalizeService
from ..services.fast_generation_flow_service import FastGenerationFlowService
from ..services.literary_generation_flow_service import LiteraryGenerationFlowService
from ..services.standard_generation_flow_service import StandardGenerationFlowService
from ..services.prompt_assembly_service import PromptAssemblyService
from ..services.prompt_compiler_service import PromptCompilerService
from ..services.narrative_verifier_service import NarrativeVerifierService
from ..services.writer_progress_service import progress_service
from ..services.writing_archive_service import WritingArchiveService
from ..services.standard_post_processing_service import StandardPostProcessingService
from ..services.version_generation_service import VersionGenerationService
from ..services.text_compression_service import TextCompressionService
from ..services.scene_generation_service import SceneGenerationService
from ..services.mission_builder_service import MissionBuilderService
from ..services.mission_pregen_service import (
    load_selected_version_id,
    mission_fingerprint,
    take_valid_pregen_mission,
)
from ..services.voice_sample_service import VoiceSampleService
from ..services.single_version_generation_service import SingleVersionGenerationService
from ..services.async_task_service import AsyncTaskService
from ..services.pipeline_config_service import PipelineConfig, PipelineConfigService
from ..services.generation_support_service import GenerationSupportService
from ..services.generation_prefetch_service import GenerationPrefetchService
from ..services.user_style_service import UserStyleService
from ..services.fingerprint_service import FingerprintService
from ..services.trajectory_analysis_service import TrajectoryAnalysisService
from ..services.generation_state import PreCollectedContext
from ..services.writer_prompt_service import WriterPromptService
from ..services.writer_shared import (
    build_blueprint_constraints_for_mission,
    generate_chapter_mission as _shared_generate_chapter_mission,
    normalize_blueprint_relationships,
    resolve_version_count as _shared_resolve_version_count,
    rewrite_with_guardrails as _shared_rewrite_with_guardrails,
)
from ..utils.json_utils import remove_think_tags, repair_json, unwrap_markdown_json

from .pipeline_review import PipelineReviewMixin

logger = logging.getLogger(__name__)


class PipelineOrchestrator(PipelineReviewMixin):
    """统一写作流水线编排器。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.novel_service = NovelService(session)

        self.context_planner = ContextPlannerService()
        self.pipeline_config_service = PipelineConfigService(session)
        self.generation_support_service = GenerationSupportService(session)
        self.evidence_router = EvidenceRouterService()
        self.generation_result_service = GenerationResultService()
        self.generation_policy_service = GenerationPolicyService()

        self.context_builder = default_context_builder
        self.guardrails = default_guardrails
        self.async_task_service = AsyncTaskService(logger)

        self.history_context_service = HistoryContextService(session, self.prompt_service, self.llm_service)
        self.context_access_service = ContextAccessService(session, self.llm_service, self.prompt_service)
        self.enhanced_context_service = EnhancedContextService()
        self.prompt_assembly_service = PromptAssemblyService(self.prompt_service, self.llm_service)
        self.prompt_compiler = PromptCompilerService()
        self.narrative_verifier = NarrativeVerifierService()
        self.mission_builder_service = MissionBuilderService(
            self.prompt_service,
            self.llm_service,
            self.generation_policy_service,
        )
        self.text_compression_service = TextCompressionService(self.llm_service)
        self.scene_generation_service = SceneGenerationService(
            self.llm_service,
            self.guardrails,
            self.generation_policy_service,
            self.text_compression_service,
        )
        self.voice_sample_service = VoiceSampleService()
        self.single_version_generation_service = SingleVersionGenerationService(
            llm_service=self.llm_service,
            guardrails=self.guardrails,
            generation_policy_service=self.generation_policy_service,
            text_compression_service=self.text_compression_service,
            preview_generation_service_factory=lambda: PreviewGenerationService(
                self.session,
                self.llm_service,
                self.prompt_service,
            ),
        )
        self.standard_post_processing_service = StandardPostProcessingService(self)
        self.version_generation_service = VersionGenerationService(self)

        self.generation_context_resolution_service = GenerationContextResolutionService(
            evidence_router=self.evidence_router,
            generation_policy_service=self.generation_policy_service,
            llm_service=self.llm_service,
            session=self.session,
        )
        self.generation_evidence_stage_service = GenerationEvidenceStageService(
            evidence_router=self.evidence_router,
            session=self.session,
            llm_service=self.llm_service,
            prompt_service=self.prompt_service,
        )
        self.generation_prompt_context_service = GenerationPromptContextService(
            prompt_service=self.prompt_service,
            context_access_service=self.context_access_service,
            prompt_assembly_service=self.prompt_assembly_service,
        )
        self.generation_prompt_stage_service = GenerationPromptStageService(
            prompt_assembly_service=self.prompt_assembly_service,
            prompt_compiler=self.prompt_compiler,
            prompt_service=self.prompt_service,
            enhanced_context_service=self.enhanced_context_service,
            llm_service=self.llm_service,
        )

        self.generation_background_task_service = GenerationBackgroundTaskService()
        self.generation_finalize_service = GenerationFinalizeService(
            generation_background_task_service=self.generation_background_task_service,
            narrative_verifier=self.narrative_verifier,
            generation_result_service=self.generation_result_service,
            generation_policy_service=self.generation_policy_service,
        )

        self.fast_generation_flow_service = FastGenerationFlowService(
            session=self.session,
            llm_service=self.llm_service,
            single_version_generation_service=self.single_version_generation_service,
            text_compression_service=self.text_compression_service,
        )
        self.literary_generation_flow_service = LiteraryGenerationFlowService(
            session=self.session,
            llm_service=self.llm_service,
            scene_generation_service=self.scene_generation_service,
            generation_policy_service=self.generation_policy_service,
            text_compression_service=self.text_compression_service,
            guardrails=self.guardrails,
        )
        self.standard_generation_flow_service = StandardGenerationFlowService(
            session=self.session,
            llm_service=self.llm_service,
            version_generation_service=self.version_generation_service,
            standard_post_processing_service=self.standard_post_processing_service,
            text_compression_service=self.text_compression_service,
        )

        self.user_style_service = UserStyleService()
        self.fingerprint_service = FingerprintService()
        self.trajectory_analysis_service = TrajectoryAnalysisService()
        self.writer_prompt_service = WriterPromptService()
        self.generation_prefetch_service = GenerationPrefetchService(
            async_task_service=self.async_task_service,
            enhanced_context_service=self.enhanced_context_service,
            context_access_service=self.context_access_service,
            evidence_router=self.evidence_router,
            trajectory_analysis_service=self.trajectory_analysis_service,
            user_style_service=self.user_style_service,
            fingerprint_service=self.fingerprint_service,
            writer_prompt_service=self.writer_prompt_service,
            context_planner=self.context_planner,
        )

        self._background_tasks = set()

    async def generate_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
        stream_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None] | None]] = None,
    ) -> Dict[str, Any]:
        total_started = time.perf_counter()

        async def _emit_stream(event: str, payload: Optional[Dict[str, Any]] = None) -> None:
            if not stream_handler:
                return
            data: Dict[str, Any] = dict(payload or {})
            data.setdefault("event", event)
            try:
                callback_result = stream_handler(data)
                if inspect.isawaitable(callback_result):
                    await callback_result
            except Exception as callback_exc:
                logger.debug("Pipeline stream_handler 回调异常（已忽略）: %s", callback_exc)

        telemetry = GenerationTelemetryService(_emit_stream)
        # 轻量 tracing：trace 级上下文，随每个阶段 span 输出
        telemetry.set_trace_context(project_id=project_id, chapter_number=chapter_number)

        # 使用 telemetry 的方法替代局部函数
        _mark_stage = telemetry.mark_stage
        async def _emit_stage(stage: str, message: Optional[str] = None) -> None:
            await telemetry.emit_stage(stage, message, chapter_number)

        # 创建进度追踪（outline_title 在后续加载，此处先用 fallback）
        await progress_service.create_progress(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_title=f"第{chapter_number}章"
        )

        # 创建写作任务档案（圣旨下达）
        archive_service = WritingArchiveService(self.session)
        try:
            archive = await archive_service.create_archive(
                project_id=project_id,
                chapter_number=chapter_number,
                user_command=None,  # 可以从 flow_config 中提取
                writing_notes=writing_notes,
            )
            archive_id = archive.id
        except Exception as archive_err:
            logger.warning(f"创建写作档案失败: {archive_err}")
            await self.session.rollback()
            archive_id = None

        await _emit_stage("starting", "开始生成章节")

        # 更新阶段：初始化完成
        await progress_service.update_stage(
            project_id, chapter_number,
            WritingStage.INIT,
            StageStatus.COMPLETED,
            progress=100,
            message="初始化完成"
        )

        # 更新阶段：需求解析开始
        await progress_service.update_stage(
            project_id, chapter_number,
            WritingStage.PARSE_REQUIREMENT,
            StageStatus.RUNNING,
            progress=10,
            message="正在解析写作需求"
        )

        raw_flow_config = flow_config or {}
        # 类型化共享状态（替代 stringly-typed dict；wire 格式仍为 dict）
        pcc = PreCollectedContext.from_dict(raw_flow_config.get("pre_collected_context"))

        stage_started = time.perf_counter()
        config = await self.pipeline_config_service.resolve_config(raw_flow_config)
        _mark_stage("resolve_config", stage_started)
        telemetry.set_trace_context(preset=config.preset)

        stage_started = time.perf_counter()
        project = await self.novel_service.ensure_project_owner(project_id, user_id)
        reference_service = ReferenceNovelLibraryService(self.session)
        project_reference_novels = await self.generation_support_service.load_project_reference_novels(project, reference_service)

        outline = await self.novel_service.get_outline(project_id, chapter_number)
        if not outline:
            raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

        chapter = await self.novel_service.get_or_create_chapter(project_id, chapter_number)
        # 生成前仅置 generating（前端轮询依赖此状态）；real_summary/selected_version_id
        # 留到成功落库时由 replace_chapter_versions 同事务清理，
        # 保证生成中途失败（LLM 报错/超时/护栏拒绝）不会毁掉已完稿章节的摘要与选中版本
        chapter.status = "generating"
        await self.session.commit()
        # 章节状态变了，项目详情缓存必须作废：GET /api/novels/{id} 走 30 分钟 TTL 的
        # 序列化缓存，而这里是直接改 ORM 对象、没经过 NovelService 的写路径，缓存不会自己
        # 失效。后果是刷新页面拿到的仍是「未生成」——「后台仍在生成」的提示永远不会出现，
        # 用户还可能对同一章再点一次生成（重复跑、重复扣费）。实测线上确实如此。
        await CacheService.invalidate_project_schema_safely(project_id)
        # onupdate=func.now() 使 updated_at 在 UPDATE 后过期；重生成时该章已在
        # project.chapters 里，后续 _serialize_project 的同步 getattr 会触发
        # 异步 IO 报 MissingGreenlet，这里显式回填避免过期访问
        await self.session.refresh(chapter, attribute_names=["updated_at"])
        _mark_stage("prepare_project_context", stage_started)

        outlines_map = {item.chapter_number: item for item in project.outlines}
        stage_started = time.perf_counter()
        history_context = pcc.history_context or {}
        if history_context:
            logger.info(
                "复用预收集历史上下文: project=%s chapter=%s",
                project_id,
                chapter_number,
            )
        else:
            history_context = await self.history_context_service.collect_history_context(
                project_id=project_id,
                chapter_number=chapter_number,
                outlines_map=outlines_map,
                chapters=project.chapters,
                user_id=user_id,
                allow_summary_backfill=not config.skip_history_summary_backfill,
            )
        _mark_stage("collect_history_context", stage_started)

        stage_started = time.perf_counter()
        project_schema = await self.novel_service._serialize_project(project, use_cache=False)
        blueprint_dict = normalize_blueprint_relationships(project_schema.blueprint.model_dump())
        pre_blueprint = pcc.blueprint
        if isinstance(pre_blueprint, dict) and pre_blueprint:
            blueprint_dict = pre_blueprint

        outline_title = outline.title or f"第{outline.chapter_number}章"
        outline_summary = outline.summary or "暂无摘要"
        # 预生成使命消费判据：用户带了写作指令就不能用预生成结果（指令会改变使命），
        # 必须在下面的默认值填充之前判定
        has_writing_notes = bool((writing_notes or "").strip())
        writing_notes = writing_notes or "无额外写作指令"
        chapter_blueprint = await self.generation_support_service.load_chapter_blueprint(project_id, chapter_number)
        planner_flow_config = {
            "preset": config.preset,
            "selected_skills": list(raw_flow_config.get("selected_skills") or []),
            "skill_policies": list(raw_flow_config.get("skill_policies") or []),
            "enable_rag": config.enable_rag,
            "enable_memory": config.enable_memory,
            "enable_state_tracking": config.enable_state_tracking,
            "enable_temporal_state": config.enable_temporal_state,
            "enable_fast_path": config.enable_fast_path,
            "enable_consistency": config.enable_consistency,
            "enable_foreshadowing": config.enable_foreshadowing,
            "enable_constitution": config.enable_constitution,
            "enable_faction": config.enable_faction,
            "enable_power_system": config.enable_power_system,
            "enable_character_relationships": config.enable_character_relationships,
            "enable_polish": config.enable_polish,
            "enable_reader_sim": config.enable_reader_sim,
            "enable_self_critique": config.enable_self_critique,
            "enable_six_dimension": config.enable_six_dimension,
            "enable_mission_brief": config.enable_mission_brief,
            "rag_mode": config.rag_mode,
            "rag_retrieval_mode": config.rag_retrieval_mode,
        }
        pre_context_plan = pcc.context_plan
        if isinstance(pre_context_plan, dict) and pre_context_plan:
            context_plan = ContextPlan.from_dict(pre_context_plan)
        else:
            context_plan = await self.context_planner.build_plan(
                project_id=project_id,
                chapter_number=chapter_number,
                writing_notes=writing_notes,
                flow_config=planner_flow_config,
                selected_skills=planner_flow_config["selected_skills"],
                skill_policies=planner_flow_config["skill_policies"],
                user_id=user_id,
                blueprint=blueprint_dict,
                outline_data={
                    "chapter_number": chapter_number,
                    "title": outline_title,
                    "summary": outline_summary,
                },
                history_context=history_context,
            )
            pcc.context_plan = context_plan.to_dict()
        context_plan_payload = context_plan.to_dict()
        await telemetry.emit_context_plan(context_plan_payload)
        fast_rag_queries = self.generation_support_service.build_fast_rag_queries(
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            chapter_blueprint=chapter_blueprint,
        )

        all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

        pattern_constraint = self.prompt_assembly_service.build_pattern_differentiation(
            history_context.get("completed_chapters", [])
        )

        visibility_context = self.context_builder.build_visibility_context(
            blueprint=blueprint_dict,
            completed_summaries=history_context["completed_summaries"],
            previous_tail=history_context["previous_tail"],
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            allowed_new_characters=[],
        )
        introduced_characters_for_mission = visibility_context["introduced_characters"]
        blueprint_constraints = build_blueprint_constraints_for_mission(
            blueprint_dict=blueprint_dict,
            outline_title=outline_title,
            outline_summary=outline_summary,
        )
        _mark_stage("build_mission_inputs", stage_started)

        # ========== Mission 生成 + 上下文准备（并行化：不依赖 Mission 的任务提前启动） ==========

        # 这一段（检索 + 使命规划）实测约 40-50 秒，此前不发任何阶段事件：
        # 前端从「开始生成章节」一路静默到写作开始，最长的一段沉默反而在最前面
        await _emit_stage("prepare_context", "检索相关剧情与设定")

        pre_rag_context = pcc.rag_context
        pre_rag_stats = pcc.rag_stats
        prefetch_tasks = self.generation_prefetch_service.schedule_prefetch_tasks(
            config=config,
            project=project,
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            blueprint_dict=blueprint_dict,
            context_plan=context_plan,
            history_context=history_context,
            fast_rag_queries=fast_rag_queries,
            pre_rag_context=pre_rag_context,
        )
        _enhanced_flow_task = prefetch_tasks.enhanced_context_task
        _memory_text_task = prefetch_tasks.memory_text_task
        _rag_task = prefetch_tasks.rag_task
        _foreshadowing_task = prefetch_tasks.foreshadowing_task
        _trajectory_task = prefetch_tasks.trajectory_task
        _user_style_task = prefetch_tasks.user_style_task
        _fingerprint_task = prefetch_tasks.fingerprint_task
        _writer_prompt_task = prefetch_tasks.writer_prompt_task

        stage_started = time.perf_counter()

        enhanced_context = {}

        # ========== Pacing Controller: 并行启动 ==========
        _pacing_task = None
        if config.enable_pacing_control:
            async def _compute_pacing() -> str:
                """计算节奏约束（纯规则，不调用 LLM）。"""
                from ..services.pacing_controller import PacingController
                try:
                    total_chapters = len(project.outlines) if project.outlines else 30
                    pacing_controller = PacingController(total_chapters)
                    pacing_controller.plan_emotion_curve()
                    pacing_info = pacing_controller.get_chapter_pacing(chapter_number)
                    if not pacing_info:
                        return ""
                    # 大纲里 LLM 逐章声明的规划字段**优先于** PacingController：
                    # 后者只按章号在通用三幕模板上取值，不知道本书实际是怎么排的；
                    # 而大纲声明的是「事件/势力/挑衅1..回击4」这套具体得多的循环结构。
                    # 是替换而非叠加——避免同一件事说两遍（约束堆叠）。
                    planned = (getattr(outline, "metadata_", None) or {}).get("planning") or {}

                    parts = ["### 节奏控制指令 (Pacing Control)"]
                    if pacing_info.get("emotion_intensity"):
                        parts.append(f"- **情绪强度**: {pacing_info['emotion_intensity']:.1f}/10")
                    narrative_phase = planned.get("narrative_phase") or pacing_info.get("narrative_phase")
                    if narrative_phase:
                        parts.append(f"- **叙事阶段**: {narrative_phase}")
                    if planned.get("emotion_hook"):
                        parts.append(f"- **本章情绪钩子**: {planned['emotion_hook']}")
                    if pacing_info.get("trend"):
                        parts.append(f"- **趋势**: {pacing_info['trend']}")
                    for advice in (pacing_info.get("pacing_advice") or []):
                        parts.append(f"- {advice}")
                    logger.info("应用Pacing Controller节奏约束于第 %d 章", chapter_number)
                    return "\n".join(parts)
                except Exception as exc:
                    logger.warning("Pacing Controller 约束生成失败: %s", exc)
                    return ""
            _pacing_task = asyncio.create_task(_compute_pacing())

        # ========== Mission 生成（与 Pacing 并行） ==========
        await _emit_stage("generate_chapter_mission", "规划本章任务")
        if config.enable_fast_path:
            # 优先尝试轻量LLM导演脚本，失败时回退到纯规则拼装
            chapter_mission = await self.mission_builder_service.build_lite_chapter_mission(
                chapter_number=chapter_number,
                outline_title=outline_title,
                outline_summary=outline_summary,
                writing_notes=writing_notes,
                previous_summary=history_context["previous_summary"],
                previous_tail=history_context["previous_tail"],
                chapter_blueprint=chapter_blueprint,
                user_id=user_id,
            )
            if chapter_mission is None:
                chapter_mission = self.mission_builder_service.build_fast_chapter_mission(
                    chapter_number=chapter_number,
                    outline_title=outline_title,
                    outline_summary=outline_summary,
                    writing_notes=writing_notes,
                    chapter_blueprint=chapter_blueprint,
                )
        else:
            # 先查选版时后台预生成的使命（mission_pregen_service）：指纹匹配且本次
            # 无写作指令 → 直接采用，免掉写作前最长的一次 LLM 等待（实测 ~120s）
            expected_fingerprint = mission_fingerprint(
                outline,
                await load_selected_version_id(self.session, project_id, chapter_number - 1),
            )
            chapter_mission, pregen_state = take_valid_pregen_mission(
                outline, expected_fingerprint, has_writing_notes
            )
            if pregen_state in {"hit", "stale_discarded"}:
                # 命中即清（一次性使用）/过期即弃都改了 outline.metadata_，立即落库：
                # 后续生成失败回滚也不允许同一份 mission 再被消费
                await self.session.commit()
            if chapter_mission is not None:
                logger.info(
                    "预生成使命命中: project=%s 章=%s", project_id, chapter_number
                )
            else:
                logger.info(
                    "预生成使命未命中(%s): project=%s 章=%s",
                    pregen_state,
                    project_id,
                    chapter_number,
                )
                # Mission 生成（内部会查 DB 加载 prompt，必须串行）
                chapter_mission = await _shared_generate_chapter_mission(
                    self.llm_service,
                    self.prompt_service,
                    blueprint_dict=blueprint_dict,
                    previous_summary=history_context["previous_summary"],
                    previous_tail=history_context["previous_tail"],
                    outline_title=outline_title,
                    outline_summary=outline_summary,
                    writing_notes=writing_notes,
                    introduced_characters=introduced_characters_for_mission,
                    all_characters=all_characters,
                    blueprint_constraints=blueprint_constraints,
                    user_id=user_id,
                    temperature=0.3,
                    pattern_constraint=pattern_constraint,
                )
        _mark_stage("generate_chapter_mission", stage_started)

        # 等待 Pacing 结果（与 Mission 并行计算完毕）并注入到 writing_notes
        if _pacing_task is not None:
            pacing_constraint = await _pacing_task
            if pacing_constraint:
                writing_notes = (writing_notes or "") + "\n\n" + pacing_constraint

        # 推送 Mission 中间产物
        await telemetry.emit_mission(chapter_mission if isinstance(chapter_mission, dict) else {})

        # 变更6: 爽点节奏验证 — 在mission生成完成后检查并可能修改mission
        coolpoint_rhythm_directive = await self.generation_support_service.validate_coolpoint_rhythm(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_mission=chapter_mission,
        )
        if coolpoint_rhythm_directive:
            logger.info("节奏纠偏触发: %s", coolpoint_rhythm_directive[:80])

        # P1 优化: Mission Brief LLM 调用提前启动（与后续 DB 操作并行）
        _mission_brief_task = None
        if chapter_mission and config.enable_mission_brief:
            _mission_brief_task = asyncio.create_task(
                self.prompt_assembly_service.generate_mission_brief(
                    chapter_mission=chapter_mission,
                    previous_summary=history_context["previous_summary"],
                    previous_tail=history_context["previous_tail"],
                    outline_title=outline_title,
                    outline_summary=outline_summary,
                    writing_notes=writing_notes,
                    introduced_characters=introduced_characters_for_mission,
                    forbidden_characters=[],  # 此时尚未计算，使用空列表
                    user_id=user_id,
                )
            )

        stage_started = time.perf_counter()
        resolved_prefetch = await self.generation_context_resolution_service.resolve_prefetch_context(
            config=config,
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            writing_notes=writing_notes,
            chapter_mission=chapter_mission,
            prefetch_tasks=prefetch_tasks,
            pre_rag_context=pre_rag_context,
            pre_rag_stats=pre_rag_stats,
            history_context=history_context,
            telemetry=telemetry,
        )
        enhanced_context = resolved_prefetch.enhanced_context
        project_memory_text = resolved_prefetch.project_memory_text
        rag_context = resolved_prefetch.rag_context
        rag_stats = resolved_prefetch.rag_stats
        writer_prompt = resolved_prefetch.writer_prompt
        _mark_stage("prepare_context", stage_started)

        allowed_new_characters = chapter_mission.get("allowed_new_characters", []) if chapter_mission else []

        # 增量更新 visibility_context：仅补充 allowed_new_characters（避免重复计算蓝图规范化和角色过滤）
        stage_started = time.perf_counter()
        if allowed_new_characters:
            _allowed_set = set(visibility_context["allowed_characters"]) | set(allowed_new_characters)
            _forbidden_set = set(all_characters) - _allowed_set
            visibility_context["allowed_characters"] = sorted(list(_allowed_set))
            visibility_context["forbidden_characters"] = sorted(list(_forbidden_set))
            # 重新裁剪蓝图中的角色和关系
            _wb = visibility_context["writer_blueprint"]
            if "characters" in _wb:
                _wb["characters"] = [
                    c for c in blueprint_dict.get("characters", [])
                    if c.get("name") in _allowed_set
                ]
            if "relationships" in _wb:
                _rels = blueprint_dict.get("relationships", [])
                _wb["relationships"] = [
                    r for r in _rels
                    if r.get("from") in _allowed_set and r.get("to") in _allowed_set
                ]
        _mark_stage("build_visibility_context", stage_started)

        writer_blueprint = visibility_context["writer_blueprint"]
        forbidden_characters = visibility_context["forbidden_characters"]
        introduced_characters = visibility_context["introduced_characters"]

        # P2 优化: Literary 声纹样本提前启动（与 memory/mission_brief 并行）
        _voice_samples_task: Optional[asyncio.Task] = None
        if config.enable_scene_by_scene and config.enable_voice_samples:
            _voice_samples_task = asyncio.create_task(
                self.voice_sample_service.generate_voice_samples(
                    characters=writer_blueprint.get("characters", []),
                    outline_summary=outline_summary,
                    chapter_mission=chapter_mission,
                    user_id=user_id,
                )
            )

        logger.info(
            "Pipeline context: project=%s chapter=%s introduced=%d allowed_new=%d forbidden=%d",
            project_id,
            chapter_number,
            len(introduced_characters),
            len(allowed_new_characters),
            len(forbidden_characters),
        )

        # Memory context 需要 introduced_characters，mission 之后才能获取
        memory_context = None
        if config.enable_memory:
            stage_started = time.perf_counter()
            memory_context = await self.generation_prompt_context_service.get_memory_context_if_enabled(
                enabled=config.enable_memory,
                project_id=project_id,
                chapter_number=chapter_number,
                introduced_characters=introduced_characters,
            )
            _mark_stage("prepare_memory_context", stage_started)

        # P1: 等待 mission brief 结果（LLM 调用已在后台运行，此处几乎零等待）
        stage_started = time.perf_counter()
        mission_brief_text = await self.generation_prompt_context_service.await_mission_brief(_mission_brief_task)
        _mark_stage("generate_mission_brief", stage_started)

        prompt_context_inputs = await self.generation_prompt_context_service.resolve_prompt_context_inputs(
            config=config,
            project=project,
            chapter_number=chapter_number,
            outline_title=outline_title,
            outline_summary=outline_summary,
            chapter_mission=chapter_mission,
            history_context=history_context,
            blueprint_dict=blueprint_dict,
        )
        total_chapters = prompt_context_inputs.total_chapters
        platinum_writing_brief = prompt_context_inputs.platinum_writing_brief
        genre_profile = prompt_context_inputs.genre_profile
        genre_prompt_injection = prompt_context_inputs.genre_prompt_injection
        genre_pacing_config = prompt_context_inputs.genre_pacing_config
        strand_info = prompt_context_inputs.strand_info
        platinum_rhythm_brief = prompt_context_inputs.platinum_rhythm_brief
        hook_continuity_brief = prompt_context_inputs.hook_continuity_brief
        emotion_expression_brief = prompt_context_inputs.emotion_expression_brief
        # Phase2: 拆包伏笔结果（brief + structured 元组）
        _fs_result = await _foreshadowing_task
        foreshadowing_structured = None
        if isinstance(_fs_result, tuple):
            foreshadowing_urgency_brief, foreshadowing_structured = _fs_result
        else:
            foreshadowing_urgency_brief = _fs_result

        # ---- 作者风格指纹（已在并行区启动） ----
        fingerprint_context: Optional[str] = None
        if _fingerprint_task is not None:
            fingerprint_context = await _fingerprint_task

        # 提取剧情推演
        evidence_stage = await self.generation_evidence_stage_service.resolve_evidence_stage(
            config=config,
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            blueprint_dict=blueprint_dict,
            history_context=history_context,
            context_plan=context_plan,
            chapter_mission=chapter_mission,
            writing_notes=writing_notes,
            project_reference_novels=project_reference_novels,
            introduced_characters=introduced_characters,
            pre_collected_context=pcc.to_dict(),
            prefetch_tasks=prefetch_tasks,
            resolved_prefetch=resolved_prefetch,
            prediction=(outline.metadata_ or {}).get("prediction"),
            telemetry=telemetry,
        )
        prediction_text = evidence_stage.prediction_text
        user_style_rules = evidence_stage.user_style_rules
        _user_style_preset = evidence_stage.user_style_preset
        fingerprint_context = evidence_stage.fingerprint_context
        trajectory_context = evidence_stage.trajectory_context
        outline_revision_context = evidence_stage.outline_revision_context
        volume_replan_context = evidence_stage.volume_replan_context
        significance_context = evidence_stage.significance_context
        chapter_state_context = evidence_stage.chapter_state_context
        power_system_context = evidence_stage.power_system_context
        relationship_context = evidence_stage.relationship_context
        foreshadowing_urgency_brief = evidence_stage.foreshadowing_urgency_brief
        foreshadowing_structured = evidence_stage.foreshadowing_structured
        retrieval_evidence_summary = evidence_stage.retrieval_evidence_summary
        writing_strategy = evidence_stage.writing_strategy
        if writing_strategy.warnings:
            logger.info("写作策略冲突: %s", "; ".join(writing_strategy.warnings))

        chapter_word_count_min, chapter_word_count_max, chapter_target_word_count = self.generation_policy_service.resolve_word_count_bounds()
        prompt_stage = await self.generation_prompt_stage_service.build_prompt_stage(
            config=config,
            context_plan=context_plan,
            writer_prompt=writer_prompt,
            writer_blueprint=writer_blueprint,
            history_context=history_context,
            chapter_mission=chapter_mission,
            mission_brief_text=mission_brief_text,
            rag_context=rag_context,
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            forbidden_characters=forbidden_characters,
            project_memory_text=project_memory_text,
            memory_context=memory_context,
            platinum_writing_brief=platinum_writing_brief,
            platinum_rhythm_brief=platinum_rhythm_brief,
            foreshadowing_urgency_brief=foreshadowing_urgency_brief,
            hook_continuity_brief=hook_continuity_brief,
            emotion_expression_brief=emotion_expression_brief,
            genre_prompt_injection=genre_prompt_injection,
            fingerprint_context=fingerprint_context,
            prediction_text=prediction_text,
            user_style_rules=user_style_rules,
            chapter_word_count_min=chapter_word_count_min,
            chapter_word_count_max=chapter_word_count_max,
            chapter_target_word_count=chapter_target_word_count,
            chapter_state_context=chapter_state_context,
            coolpoint_rhythm_directive=coolpoint_rhythm_directive,
            writing_strategy=writing_strategy,
            power_system_context=power_system_context,
            relationship_context=relationship_context,
            trajectory_context=trajectory_context,
            outline_revision_context=outline_revision_context,
            volume_replan_context=volume_replan_context,
            significance_context=significance_context,
            project=project,
            chapter_number=chapter_number,
            project_reference_novels=project_reference_novels,
            reference_service=reference_service,
            enhanced_context=enhanced_context,
        )
        prompt_sections = prompt_stage.prompt_sections
        prompt_compile_summary = prompt_stage.prompt_compile_summary
        prompt_input = prompt_stage.prompt_input
        writer_prompt = prompt_stage.writer_prompt
        reference_prose_text = prompt_stage.reference_prose_text
        fusion_dna_text = prompt_stage.fusion_dna_text
        await telemetry.emit_prompt_compile_summary(prompt_compile_summary)
        logger.debug("Pipeline prompt length: %s chars", len(prompt_input))

        _mark_stage("build_generation_prompt", stage_started)
        await _emit_stage("build_generation_prompt", "完成上下文组装，开始写作")

        # ========== Literary 模式：场景级分步生成 ==========
        if config.enable_scene_by_scene:
            await _emit_stage("generate_scene_by_scene", "按场景分步生成中")
            # 关键路径软预算：与标准分支同一起点(total_started)、同一预算配置；只约束
            # literary 后处理链（雕塑/人味化/扩写/质检），场景生成本体不受预算约束。
            _literary_budget_sec = getattr(settings, "generation_time_budget_sec", 0) or 0
            literary_deadline = (total_started + _literary_budget_sec) if _literary_budget_sec > 0 else None
            literary_result = await self.literary_generation_flow_service.run(
                voice_samples_task=_voice_samples_task,
                context_plan=context_plan,
                prompt_compiler=self.prompt_compiler,
                prompt_sections_data={
                    "chapter_goals": f"[当前章节目标]\n标题：{outline_title}\n摘要：{outline_summary}\n写作指令：{writing_notes}",
                    "mission_brief": mission_brief_text or "",
                    "director_script": json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else "",
                    "story_skeleton": history_context.get("story_skeleton", ""),
                    "previous_summary": history_context["previous_summary"],
                    "previous_tail": history_context["previous_tail"],
                    "writer_blueprint": json.dumps(writer_blueprint, ensure_ascii=False, indent=2)[:3000],
                    "forbidden_characters": ", ".join(forbidden_characters) if forbidden_characters else "",
                    "reference_prose": reference_prose_text,
                    "fusion_dna": fusion_dna_text,
                },
                writer_prompt=writer_prompt,
                chapter_mission=chapter_mission,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                user_id=user_id,
                genre_profile=genre_profile,
                chapter_word_count_max=chapter_word_count_max,
                chapter_target_word_count=chapter_target_word_count,
                chapter_word_count_min=chapter_word_count_min,
                config=config,
                outline_title=outline_title,
                history_context=history_context,
                project_id=project_id,
                chapter_number=chapter_number,
                enhanced_context=enhanced_context,
                run_enrichment=self._run_enrichment,
                run_quality_detection=self._run_quality_detection,
                mark_stage=_mark_stage,
                deadline=literary_deadline,
            )
            version = literary_result.version
            best_content = literary_result.best_content
            review_summaries = literary_result.review_summaries
            six_dimension_payload = literary_result.six_dimension_payload

            # 持久化
            await _emit_stage("persist_versions", "写入章节版本中")
            contents = [version["content"]]
            metadata_list = [version.get("metadata")]
            stage_started = time.perf_counter()
            versions_models = await self.novel_service.replace_chapter_versions(chapter, contents, metadata_list)
            _mark_stage("persist_versions", stage_started)

            self.generation_finalize_service.schedule_followups(
                task_registry=self._background_tasks,
                versions_models=versions_models,
                best_version_index=0,
                project_id=project_id,
                chapter=chapter,
                chapter_number=chapter_number,
                best_content=best_content,
                introduced_characters=introduced_characters,
                user_id=user_id,
                enable_memory=config.enable_memory,
                enable_state_tracking=config.enable_state_tracking,
                enable_outline_revision=config.enable_outline_revision,
                enable_volume_retrospective=config.enable_volume_retrospective,
                enable_character_significance=config.enable_character_significance,
                six_dimension_payload=six_dimension_payload,
            )

            variants = self.generation_finalize_service.build_single_variant(
                version_model=versions_models[0],
                version=version,
            )
            telemetry.stage_timings_ms["total_pipeline"] = int((time.perf_counter() - total_started) * 1000)

            await self.generation_finalize_service.complete_progress(
                project_id=project_id,
                chapter_number=chapter_number,
                message="章节生成完成",
            )

            # 完成写作任务档案（奏章批复）
            await self.generation_finalize_service.complete_archive(
                archive_service=archive_service,
                archive_id=archive_id,
                variants=variants,
                versions_models=versions_models,
                best_version_index=0,
                version_count=1,
                gatekeeper_score=None,
                warning_label="Literary模式完成写作档案失败",
            )

            return await self.generation_finalize_service.finalize_response(
                plan=context_plan,
                chapter_text=best_content,
                review_summaries=review_summaries,
                retrieval_evidence_summary=retrieval_evidence_summary,
                versions=[version],
                variants=variants,
                best_version_index=0,
                telemetry=telemetry,
                emit_completed=lambda: telemetry.emit_completed(chapter_number),
                project_id=project_id,
                chapter_number=chapter_number,
                preset=config.preset,
                mode="literary_scene_by_scene",
                config=config,
                rag_stats=rag_stats,
                context_plan_payload=context_plan_payload,
                prompt_compile_summary=prompt_compile_summary,
                stage_timings_ms=telemetry.stage_timings_ms,
                strategy_warnings=writing_strategy.warnings,
            )

        if config.enable_fast_path:
            await _emit_stage("generate_fast_version", "快速模式：生成正文中")

            async def _stream_fast_text_delta(delta: str) -> None:
                await telemetry.emit_text_delta(delta, "generate_fast_version", chapter_number)

            fast_result = await self.fast_generation_flow_service.run(
                prompt_input=prompt_input,
                writer_prompt=writer_prompt,
                project_id=project_id,
                chapter_number=chapter_number,
                outline_title=outline_title,
                outline_summary=outline_summary,
                chapter_mission=chapter_mission,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                user_id=user_id,
                writer_blueprint=writer_blueprint,
                memory_context=memory_context,
                enhanced_context=enhanced_context,
                config=config,
                chapter_target_word_count=chapter_target_word_count,
                chapter_word_count_max=chapter_word_count_max,
                genre_profile=genre_profile,
                history_context=history_context,
                emit_text_delta=_stream_fast_text_delta if stream_handler else None,
                mark_stage=_mark_stage,
                run_polish=self._run_polish,
            )
            version = fast_result.version
            best_content = fast_result.best_content
            review_summaries = fast_result.review_summaries
            _stage_b_params = fast_result.stage_b_params

            stage_started = time.perf_counter()
            await _emit_stage("persist_versions", "写入章节版本中")
            versions_models = await self.novel_service.replace_chapter_versions(
                chapter,
                [version["content"]],
                [version.get("metadata")],
            )
            _mark_stage("persist_versions", stage_started)

            self.generation_finalize_service.schedule_followups(
                task_registry=self._background_tasks,
                versions_models=versions_models,
                best_version_index=0,
                project_id=project_id,
                chapter=chapter,
                chapter_number=chapter_number,
                best_content=best_content,
                introduced_characters=introduced_characters,
                user_id=user_id,
                enable_memory=config.enable_memory,
                enable_state_tracking=config.enable_state_tracking,
                enable_outline_revision=config.enable_outline_revision,
                enable_volume_retrospective=config.enable_volume_retrospective,
                enable_character_significance=config.enable_character_significance,
                stage_b_params=_stage_b_params,
            )

            variants = self.generation_finalize_service.build_single_variant(
                version_model=versions_models[0],
                version=version,
            )
            telemetry.stage_timings_ms["total_pipeline"] = int((time.perf_counter() - total_started) * 1000)

            await self.generation_finalize_service.complete_progress(
                project_id=project_id,
                chapter_number=chapter_number,
                message="章节生成完成",
            )

            await self.generation_finalize_service.complete_archive(
                archive_service=archive_service,
                archive_id=archive_id,
                variants=variants,
                versions_models=versions_models,
                best_version_index=0,
                version_count=1,
                gatekeeper_score=None,
                warning_label="Fast模式完成写作档案失败",
            )

            return await self.generation_finalize_service.finalize_response(
                plan=context_plan,
                chapter_text=best_content,
                review_summaries=review_summaries,
                retrieval_evidence_summary=retrieval_evidence_summary,
                versions=[version],
                variants=variants,
                best_version_index=0,
                telemetry=telemetry,
                emit_completed=lambda: telemetry.emit_completed(chapter_number),
                project_id=project_id,
                chapter_number=chapter_number,
                preset=config.preset,
                mode="fast_single_pass",
                config=config,
                rag_stats=rag_stats,
                context_plan_payload=context_plan_payload,
                prompt_compile_summary=prompt_compile_summary,
                stage_timings_ms=telemetry.stage_timings_ms,
                strategy_warnings=writing_strategy.warnings,
            )

        # ========== 标准模式：多版本并行生成 ==========
        await _emit_stage("generate_versions", "多版本生成中")

        # 草稿流式（2026-08-12）：standard/premium 此前是分钟级黑盒（仅阶段事件），
        # 现复用 fast 的 text_delta 管道把草稿逐字流给前端；version_count>1 时
        # 由 VersionGenerationService 自动关闭（并行 delta 交错无意义）。
        async def _stream_standard_text_delta(delta: str) -> None:
            await telemetry.emit_text_delta(delta, "generate_versions", chapter_number)
        # 关键路径软预算：从生成总起点(total_started, perf_counter)起算，超过即让后处理链
        # 跳过剩余可选步骤、带当前最佳稿返回，避免后处理把整章拖到 600s 硬超时而全盘失败。
        _budget_sec = getattr(settings, "generation_time_budget_sec", 0) or 0
        postproc_deadline = (total_started + _budget_sec) if _budget_sec > 0 else None
        standard_result = await self.standard_generation_flow_service.run(
            prompt_input=prompt_input,
            prompt_sections=prompt_sections,
            writer_prompt=writer_prompt,
            enhanced_context=enhanced_context,
            config=config,
            project_id=project_id,
            chapter_number=chapter_number,
            outline_title=outline_title,
            outline_summary=outline_summary,
            chapter_mission=chapter_mission,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            user_id=user_id,
            writer_blueprint=writer_blueprint,
            memory_context=memory_context,
            chapter_target_word_count=chapter_target_word_count,
            chapter_word_count_min=chapter_word_count_min,
            chapter_word_count_max=chapter_word_count_max,
            genre_profile=genre_profile,
            history_context=history_context,
            mark_stage=_mark_stage,
            deadline=postproc_deadline,
            emit_text_delta=_stream_standard_text_delta if stream_handler else None,
            # 后处理链逐步播报：这条链约占一章四成时长，此前对前端完全静默，
            # 阶段停在「多版本生成中」不动，用户只能理解为卡死
            emit_stage=_emit_stage if stream_handler else None,
        )
        version_count = config.version_count
        versions = standard_result.versions
        best_version_index = standard_result.best_version_index
        ai_review_result = standard_result.ai_review_result
        best_content = standard_result.best_content
        review_summaries = standard_result.review_summaries
        _stage_b_params = standard_result.stage_b_params

        contents = [v.get("content", "") for v in versions]
        metadata = [v.get("metadata") for v in versions]
        await _emit_stage("persist_versions", "写入章节版本中")
        stage_started = time.perf_counter()
        versions_models = await self.novel_service.replace_chapter_versions(chapter, contents, metadata)
        _mark_stage("persist_versions", stage_started)

        stage_started = time.perf_counter()
        # 名字要如实：这里只是排队后续异步任务（stage-B 分析/记忆/入库），并不跑六维评审。
        # 旧名 schedule_async_six_dimension 会让人把链内那次同步六维评审的耗时错记到别处。
        _mark_stage("schedule_async_followups", stage_started)

        self.generation_finalize_service.schedule_followups(
            task_registry=self._background_tasks,
            versions_models=versions_models,
            best_version_index=best_version_index,
            project_id=project_id,
            chapter=chapter,
            chapter_number=chapter_number,
            best_content=best_content,
            introduced_characters=introduced_characters,
            user_id=user_id,
            enable_memory=config.enable_memory,
            enable_state_tracking=config.enable_state_tracking,
            enable_outline_revision=config.enable_outline_revision,
            enable_volume_retrospective=config.enable_volume_retrospective,
            enable_character_significance=config.enable_character_significance,
            stage_b_params=_stage_b_params,
            run_post_processor=True,
        )

        variants = self.generation_finalize_service.build_variants(
            versions_models=versions_models,
            versions=versions,
        )

        telemetry.stage_timings_ms["total_pipeline"] = int((time.perf_counter() - total_started) * 1000)

        await self.generation_finalize_service.complete_progress(
            project_id=project_id,
            chapter_number=chapter_number,
            message=f"生成{version_count}个版本",
        )

        await self.generation_finalize_service.complete_archive(
            archive_service=archive_service,
            archive_id=archive_id,
            variants=variants,
            versions_models=versions_models,
            best_version_index=best_version_index,
            version_count=version_count,
            gatekeeper_score=(ai_review_result or {}).get("score") if isinstance(ai_review_result, dict) else None,
            warning_label="完成写作档案失败",
        )

        return await self.generation_finalize_service.finalize_response(
            plan=context_plan,
            chapter_text=best_content if versions else "",
            review_summaries=review_summaries,
            retrieval_evidence_summary=retrieval_evidence_summary,
            versions=versions,
            variants=variants,
            best_version_index=best_version_index,
            telemetry=telemetry,
            emit_completed=lambda: telemetry.emit_completed(chapter_number),
            project_id=project_id,
            chapter_number=chapter_number,
            preset=config.preset,
            mode=None,
            config=config,
            rag_stats=rag_stats,
            context_plan_payload=context_plan_payload,
            prompt_compile_summary=prompt_compile_summary,
            stage_timings_ms=telemetry.stage_timings_ms,
            strategy_warnings=writing_strategy.warnings,
        )

__all__ = ["PipelineOrchestrator", "PipelineConfig"]
