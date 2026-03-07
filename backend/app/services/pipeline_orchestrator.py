# AIMETA P=写作流水线编排_统一生成入口|R=上下文汇聚_生成_审查_优化|NR=不含API路由|E=PipelineOrchestrator|X=internal|A=编排器|D=fastapi,sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.constants import CHAPTER_MAX_WORDS, CHAPTER_MIN_WORDS, StageStatus, WritingStage
from ..db.init_db import repair_schema_if_needed
from ..db.session import AsyncSessionLocal
from ..models.chapter_blueprint import ChapterBlueprint
from ..models.novel import Chapter, ChapterVersion, NovelProject
from ..models.reference_novel import ReferenceNovel
from ..repositories.system_config_repository import SystemConfigRepository
from ..services.chapter_guardrails import default_guardrails
from ..services.enhanced_writing_flow import EnhancedWritingFlow
from ..services.llm_service import LLMService
from ..services.novel_service import NovelService
from ..services.preview_generation_service import PreviewGenerationService
from ..services.reference_novel_library_service import ReferenceNovelLibraryService
from ..services.prompt_service import PromptService
from ..services.writer_context_builder import default_context_builder
from ..services.writer_progress_service import progress_service
from ..services.writer_shared import (
    build_blueprint_constraints_for_mission,
    generate_chapter_mission as _shared_generate_chapter_mission,
    normalize_blueprint_relationships,
    resolve_version_count as _shared_resolve_version_count,
    rewrite_with_guardrails as _shared_rewrite_with_guardrails,
)
from ..services.platinum_writing_context import (
    PLATINUM_WRITING_BRIEF_FALLBACK,
    build_foreshadowing_urgency_brief,
    build_hook_continuity_brief,
    build_platinum_rhythm_brief,
)
from ..utils.json_utils import extract_text_from_json, remove_think_tags, repair_json, sanitize_chapter_plain_text, unwrap_markdown_json

from .pipeline_context import PipelineContextMixin
from .pipeline_prompt import PipelinePromptMixin
from .pipeline_review import PipelineReviewMixin

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    preset: str = "basic"
    version_count: int = 2
    enable_preview: bool = False
    enable_optimizer: bool = False
    enable_consistency: bool = False
    enable_enrichment: bool = False
    async_finalize: bool = False
    enable_constitution: bool = False
    enable_persona: bool = False
    enable_six_dimension: bool = False
    enable_reader_sim: bool = False
    enable_self_critique: bool = False
    enable_memory: bool = False
    enable_rag: bool = True
    rag_mode: str = "simple"
    enable_foreshadowing: bool = False
    enable_faction: bool = False
    enable_anti_hallucination: bool = False
    rag_retrieval_mode: str = "vector"
    pacing_model: str = "default"
    enable_humanization: bool = False
    humanization_threshold: int = 70
    enable_lightweight_humanization: bool = False  # fast 模式：scan + 规则替换，无 LLM
    enable_fingerprint: bool = False
    enable_polish: bool = False
    enable_mission_brief: bool = False
    enable_density_compression: bool = False
    # Literary mode features (改进 1-10)
    enable_scene_by_scene: bool = False
    enable_prose_sculpting: bool = False
    enable_golden_paragraph: bool = False
    enable_reference_prose: bool = False
    enable_voice_samples: bool = False
    enable_narrative_variety: bool = False
    use_slim_prompt: bool = False
    literary_adaptive_postprocess: bool = True
    enable_fast_path: bool = False
    disable_guardrail_rewrite: bool = False
    skip_history_summary_backfill: bool = False
    use_local_anti_hallucination: bool = False


class PipelineOrchestrator(PipelineContextMixin, PipelinePromptMixin, PipelineReviewMixin):
    """统一写作流水线编排器。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.novel_service = NovelService(session)
        self.context_builder = default_context_builder
        self.guardrails = default_guardrails
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
        stage_timings_ms: Dict[str, int] = {}

        def _mark_stage(stage_name: str, started_at: float) -> None:
            stage_timings_ms[stage_name] = int((time.perf_counter() - started_at) * 1000)

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

        async def _emit_stage(stage: str, message: Optional[str] = None) -> None:
            await _emit_stream(
                "stage",
                {
                    "stage": stage,
                    "message": message or stage,
                    "chapter_number": chapter_number,
                },
            )

        # 创建进度追踪
        await progress_service.create_progress(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_title=outline_title if 'outline_title' in dir() else f"第{chapter_number}章"
        )

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

        stage_started = time.perf_counter()
        config = await self._resolve_config(flow_config)
        _mark_stage("resolve_config", stage_started)

        stage_started = time.perf_counter()
        project = await self.novel_service.ensure_project_owner(project_id, user_id)
        reference_service = ReferenceNovelLibraryService(self.session)
        project_reference_novels = await self._load_project_reference_novels(project, reference_service)

        outline = await self.novel_service.get_outline(project_id, chapter_number)
        if not outline:
            raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

        chapter = await self.novel_service.get_or_create_chapter(project_id, chapter_number)
        chapter.real_summary = None
        chapter.selected_version_id = None
        chapter.status = "generating"
        await self.session.commit()
        _mark_stage("prepare_project_context", stage_started)

        outlines_map = {item.chapter_number: item for item in project.outlines}
        stage_started = time.perf_counter()
        history_context = await self._collect_history_context(
            project_id=project_id,
            chapter_number=chapter_number,
            outlines_map=outlines_map,
            chapters=project.chapters,
            user_id=user_id,
            allow_summary_backfill=not config.skip_history_summary_backfill,
        )
        _mark_stage("collect_history_context", stage_started)

        stage_started = time.perf_counter()
        project_schema = await self.novel_service._serialize_project(project)
        blueprint_dict = normalize_blueprint_relationships(project_schema.blueprint.model_dump())

        outline_title = outline.title or f"第{outline.chapter_number}章"
        outline_summary = outline.summary or "暂无摘要"
        writing_notes = writing_notes or "无额外写作指令"
        chapter_blueprint = await self._load_chapter_blueprint(project_id, chapter_number)
        fast_rag_queries = self._build_fast_rag_queries(
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            chapter_blueprint=chapter_blueprint,
        )

        all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

        pattern_constraint = self._build_pattern_differentiation(
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

        # 提前启动不依赖 Mission 输出的任务（使用独立会话避免 session 并发）
        _need_enhanced = (
            config.enable_constitution or config.enable_persona
            or config.enable_foreshadowing or config.enable_faction
        )
        _enhanced_flow_task: Optional[asyncio.Task] = None
        if _need_enhanced:
            async def _parallel_enhanced_flow():
                async with AsyncSessionLocal() as bg_session:
                    bg_llm = LLMService(bg_session)
                    bg_prompt = PromptService(bg_session)
                    flow = EnhancedWritingFlow(bg_session, bg_llm, bg_prompt)
                    ctx = await flow.prepare_writing_context(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_outline=outline_summary,
                    )
                    return flow, ctx
            _enhanced_flow_task = asyncio.create_task(_parallel_enhanced_flow())

        _memory_text_task: Optional[asyncio.Task] = None
        async def _parallel_project_memory():
            async with AsyncSessionLocal() as bg_session:
                from ..models.project_memory import ProjectMemory
                _result = await bg_session.execute(
                    select(ProjectMemory).where(ProjectMemory.project_id == project_id)
                )
                memory = _result.scalars().first()
                if not memory:
                    return None
                parts = []
                if memory.global_summary:
                    parts.append(f"### 全局摘要\n{memory.global_summary}")
                if memory.plot_arcs:
                    parts.append("### 剧情线追踪\n" + json.dumps(memory.plot_arcs, ensure_ascii=False, indent=2))
                return "\n\n".join(parts) if parts else None
        _memory_text_task = asyncio.create_task(_parallel_project_memory())

        _rag_task: Optional[asyncio.Task] = None
        if config.enable_rag and config.rag_mode != "two_stage":
            # simple RAG 不依赖 Mission 输出，可并行（使用独立会话避免 session 竞态）
            async def _parallel_rag():
                async with AsyncSessionLocal() as bg_session:
                    bg_llm = LLMService(bg_session)
                    from .writer_shared import create_vector_store_or_none
                    from .chapter_context_service import ChapterContextService
                    if not settings.vector_store_enabled:
                        return {"chunks": [], "summaries": []}
                    vector_store = create_vector_store_or_none()
                    if vector_store is None:
                        return {"chunks": [], "summaries": []}
                    if config.enable_fast_path and fast_rag_queries:
                        query_parts = fast_rag_queries[:]
                    else:
                        query_parts = [outline_title, outline_summary]
                        if writing_notes:
                            query_parts.append(writing_notes)
                    rag_query = "\n".join(part for part in query_parts if part)
                    context_service = ChapterContextService(llm_service=bg_llm, vector_store=vector_store)
                    rag_result = await context_service.retrieve_for_generation(
                        project_id=project_id,
                        query_text=rag_query or outline_title or outline_summary,
                        user_id=user_id,
                        retrieval_mode=config.rag_retrieval_mode,
                    )
                    return {
                        "chunks": rag_result.chunk_texts() if rag_result.chunks else [],
                        "summaries": rag_result.summary_lines() if rag_result.summaries else [],
                    }
            _rag_task = asyncio.create_task(_parallel_rag())

        # 优化项3: 提前启动不依赖 Mission 的上下文构建任务（使用独立 session）
        async def _parallel_foreshadowing():
            async with AsyncSessionLocal() as bg_session:
                return await build_foreshadowing_urgency_brief(
                    session=bg_session,
                    project_id=project_id,
                    chapter_number=chapter_number,
                )
        _foreshadowing_task = asyncio.create_task(_parallel_foreshadowing())

        async def _parallel_user_style():
            try:
                async with AsyncSessionLocal() as bg_session:
                    from sqlalchemy import select as sa_select
                    from ..models.user_writing_preference import UserWritingPreference
                    from ..core.writing_style_presets import build_user_style_prompt
                    result = await bg_session.execute(
                        sa_select(UserWritingPreference).where(UserWritingPreference.user_id == user_id)
                    )
                    pref = result.scalars().first()
                    if pref:
                        rules = build_user_style_prompt(pref)
                        logger.info("用户 %s 已加载写作风格偏好 (preset=%s)", user_id, pref.style_preset)
                        return rules
                    return None
            except Exception as e:
                logger.warning("加载用户写作风格偏好失败（不影响生成）: %s", e)
                return None
        _user_style_task = asyncio.create_task(_parallel_user_style())

        _fingerprint_task: Optional[asyncio.Task] = None
        if config.enable_fingerprint:
            def _sync_fingerprint():
                try:
                    from .author_fingerprint_service import AuthorFingerprintService
                    fp_service = AuthorFingerprintService()
                    chapter_texts = [
                        ch.selected_version.content
                        for ch in project.chapters
                        if ch.chapter_number < chapter_number
                        and ch.selected_version
                        and ch.selected_version.content
                    ]
                    return fp_service.get_or_extract(project_id, chapter_texts)
                except Exception as e:
                    logger.warning("风格指纹提取失败（不影响生成）: %s", e)
                    return None
            loop = asyncio.get_event_loop()
            _fingerprint_task = asyncio.create_task(
                loop.run_in_executor(None, _sync_fingerprint)
            )

        # 优化项4: writer prompt 提前加载（利用全局缓存，与 Mission 并行）
        async def _parallel_writer_prompt():
            async with AsyncSessionLocal() as bg_session:
                bg_prompt = PromptService(bg_session)
                if config.enable_fast_path:
                    p = await bg_prompt.get_prompt("writing_fast")
                    if p:
                        return p
                p = await bg_prompt.get_prompt("writing_v2")
                if p:
                    return p
                p = await bg_prompt.get_prompt("writing")
                return p
        _writer_prompt_task = asyncio.create_task(_parallel_writer_prompt())

        stage_started = time.perf_counter()

        if config.enable_fast_path:
            chapter_mission = self._build_fast_chapter_mission(
                chapter_number=chapter_number,
                outline_title=outline_title,
                outline_summary=outline_summary,
                writing_notes=writing_notes,
                chapter_blueprint=chapter_blueprint,
            )
        else:
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

        # P1 优化: Mission Brief LLM 调用提前启动（与后续 DB 操作并行）
        _mission_brief_task = None
        if chapter_mission and config.enable_mission_brief:
            _mission_brief_task = asyncio.create_task(
                self._generate_mission_brief(
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

        # ========== 等待并行任务完成 + 处理依赖 Mission 的上下文 ==========
        stage_started = time.perf_counter()
        enhanced_flow = None
        enhanced_context = None
        if _enhanced_flow_task is not None:
            enhanced_flow, enhanced_context = await _enhanced_flow_task

        project_memory_text = await _memory_text_task

        rag_context = None
        knowledge_context = None
        rag_stats = None
        if config.enable_rag:
            if config.rag_mode == "two_stage":
                # two_stage 模式依赖 Mission 的 pov_character，只能在 Mission 之后执行
                knowledge_context, rag_stats = await self._get_two_stage_rag_context(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    writing_notes=writing_notes,
                    pov_character=self._resolve_pov_character(chapter_mission),
                    user_id=user_id,
                    retrieval_mode=config.rag_retrieval_mode,
                )
            elif _rag_task is not None:
                rag_context = await _rag_task
                rag_stats = {
                    "mode": "simple",
                    "chunks": len(rag_context.get("chunks", [])) if rag_context else 0,
                    "summaries": len(rag_context.get("summaries", [])) if rag_context else 0,
                }

        writer_prompt = await _writer_prompt_task
        if not writer_prompt:
            raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置")
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
                self._generate_voice_samples(
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
            memory_context = await self._get_memory_context(
                project_id=project_id,
                chapter_number=chapter_number,
                involved_characters=introduced_characters,
            )
            _mark_stage("prepare_memory_context", stage_started)

        # P1: 等待 mission brief 结果（LLM 调用已在后台运行，此处几乎零等待）
        mission_brief_text = None
        if _mission_brief_task is not None:
            stage_started = time.perf_counter()
            try:
                mission_brief_text = await _mission_brief_task
            except Exception as e:
                logger.warning("Mission brief 生成失败（不影响生成）: %s", e)
            _mark_stage("generate_mission_brief", stage_started)

        total_chapters = max(
            chapter_number,
            max((item.chapter_number for item in project.outlines), default=chapter_number),
        )
        platinum_writing_brief = (
            await self.prompt_service.get_prompt("platinum_writing_brief")
            or PLATINUM_WRITING_BRIEF_FALLBACK
        )

        # 题材自适应：加载 genre profile
        genre_profile = None
        genre_prompt_injection = ""
        genre_pacing_config = None
        if getattr(settings, "enable_genre_adaptation", True):
            genre_name = blueprint_dict.get("genre") or ""
            if genre_name:
                from .genre_profile_service import GenreProfileService
                genre_profile = GenreProfileService.get_profile(genre_name)
                if genre_profile:
                    genre_prompt_injection = GenreProfileService.build_genre_prompt_injection(genre_profile)
                    genre_pacing_config = genre_profile.get("pacing_config")

        # Strand Weave：获取线团分配
        strand_info = None
        if config.pacing_model == "strand_weave":
            from .strand_weave_service import StrandWeaveService
            sws_kwargs = {}
            if genre_pacing_config:
                sws_kwargs = {
                    "quest_ratio": genre_pacing_config.get("quest_ratio", settings.strand_quest_ratio),
                    "fire_ratio": genre_pacing_config.get("fire_ratio", settings.strand_fire_ratio),
                    "constellation_ratio": genre_pacing_config.get("constellation_ratio", settings.strand_constellation_ratio),
                }
            else:
                sws_kwargs = {
                    "quest_ratio": settings.strand_quest_ratio,
                    "fire_ratio": settings.strand_fire_ratio,
                    "constellation_ratio": settings.strand_constellation_ratio,
                }
            strand_service = StrandWeaveService(
                total_chapters=total_chapters,
                interleave_interval=settings.strand_interleave_interval,
                **sws_kwargs,
            )
            strand_service.plan_strands()
            strand_info = strand_service.get_chapter_strand(chapter_number)

        platinum_rhythm_brief = build_platinum_rhythm_brief(
            chapter_number=chapter_number,
            total_chapters=total_chapters,
            outline_title=outline_title,
            outline_summary=outline_summary,
            chapter_mission=chapter_mission,
            genre_pacing_config=genre_pacing_config,
            strand_info=strand_info,
        )
        foreshadowing_urgency_brief = await _foreshadowing_task
        hook_continuity_brief = build_hook_continuity_brief(
            previous_summary=history_context["previous_summary"],
            previous_tail=history_context["previous_tail"],
            chapter_mission=chapter_mission,
        )
        emotion_expression_brief = self._build_emotion_expression_brief(
            history_context.get("completed_chapters", [])
        )

        # ---- 作者风格指纹（已在并行区启动） ----
        fingerprint_context: Optional[str] = None
        if _fingerprint_task is not None:
            fingerprint_context = await _fingerprint_task

        # 提取剧情推演
        prediction = (outline.metadata_ or {}).get("prediction")
        prediction_text = ""
        if prediction:
            _labels = {"key_points": "章节要点", "cool_points": "爽点设计", "foreshadowing_hooks": "伏笔/钩子", "foreshadowing_targets": "需回收伏笔", "limitations": "写作限制"}
            prediction_text = "\n".join(
                f"{label}：\n" + "\n".join(f"- {item}" for item in prediction.get(key, []))
                for key, label in _labels.items() if prediction.get(key)
            )
            # 追加 beats 节拍编排
            beats = prediction.get("beats")
            if beats:
                _beat_type_labels = {"setup": "铺垫", "provoke": "激化", "twist": "转折", "payoff": "爆发", "hook": "悬念"}
                beats_lines = []
                for idx, b in enumerate(beats, 1):
                    beat_type = _beat_type_labels.get(b.get("type", ""), b.get("type", ""))
                    content = b.get("content", "")
                    emotion = b.get("emotion", "")
                    beats_lines.append(f"{idx}. [{beat_type}] {content} ({emotion})")
                prediction_text += "\n节拍编排：\n" + "\n".join(beats_lines)

        # ---- 用户写作风格偏好（已在并行区启动） ----
        user_style_rules = await _user_style_task

        chapter_word_count_min, chapter_word_count_max, chapter_target_word_count = self._resolve_word_count_bounds()
        prompt_sections = self._build_prompt_sections(
            writer_blueprint=writer_blueprint,
            previous_summary=history_context["previous_summary"],
            previous_tail=history_context["previous_tail"],
            chapter_mission=chapter_mission,
            mission_brief_text=mission_brief_text,
            rag_context=rag_context,
            knowledge_context=knowledge_context,
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
            story_skeleton=history_context.get("story_skeleton"),
            genre_prompt_injection=genre_prompt_injection,
            fingerprint_context=fingerprint_context,
            prediction_text=prediction_text,
            user_style_rules=user_style_rules,
            chapter_word_count_min=chapter_word_count_min,
            chapter_word_count_max=chapter_word_count_max,
            chapter_target_word_count=chapter_target_word_count,
        )

        # ---- Literary 模式：范文注入 + 叙事多样性约束 ----
        reference_prose_text = ""
        if config.enable_reference_prose:
            try:
                from .reference_prose_service import ReferenceProseService
                refs = ReferenceProseService.select_references(
                    outline_summary,
                    chapter_mission,
                    project_reference_novels=project_reference_novels,
                )
                reference_prose_text = ReferenceProseService.format_for_prompt(refs)
                if reference_prose_text:
                    prompt_sections.append(("[风格参考]", reference_prose_text))
                    if project_reference_novels:
                        style_samples = reference_service.format_style_samples_for_prompt(project_reference_novels)
                        if style_samples:
                            prompt_sections.append(("[库风格样本]", style_samples))
                        memory_card_text = reference_service.format_memory_card_for_prompt(project_reference_novels)
                        if memory_card_text:
                            prompt_sections.append(("[参考小说创作指导]", memory_card_text))
            except Exception as e:
                logger.warning("范文注入失败（不影响生成）: %s", e)

        # ---- 融合DNA注入：替代原始拼接，提供统一的风格和结构指引 ----
        fusion_dna_text = ""
        if hasattr(project, 'fusion_dna') and project.fusion_dna:
            fusion_dna_text = reference_service.format_fusion_dna_for_prompt(project.fusion_dna)
            if fusion_dna_text:
                prompt_sections.append(("[创作DNA融合指引]", fusion_dna_text))

        narrative_variety_text = ""
        if config.enable_narrative_variety:
            try:
                from .narrative_variety_tracker import NarrativeVarietyTracker, ChapterPattern
                recent_patterns = []
                for ch in sorted(project.chapters, key=lambda c: c.chapter_number):
                    if ch.chapter_number < chapter_number and ch.selected_version:
                        ch_mission = (ch.selected_version.metadata_ or {}).get("chapter_mission")
                        pattern = ChapterPattern.from_mission_and_text(
                            ch.chapter_number, ch_mission, ch.selected_version.content
                        )
                        recent_patterns.append(pattern)

                if len(recent_patterns) >= 2:
                    tracker = NarrativeVarietyTracker()
                    variety_constraints = tracker.analyze_variety(recent_patterns, chapter_number)
                    structure_suggestion = tracker.suggest_structure(recent_patterns, chapter_mission)
                    variety_constraints.update(structure_suggestion)
                    narrative_variety_text = tracker.format_constraints_for_prompt(variety_constraints)
                    if narrative_variety_text:
                        prompt_sections.append(("[叙事差异化约束]", narrative_variety_text))
            except Exception as e:
                logger.warning("叙事多样性追踪失败（不影响生成）: %s", e)

        if enhanced_flow and enhanced_context:
            prompt_sections = enhanced_flow.build_enhanced_prompt_sections(prompt_sections, enhanced_context)

        # P5 优化: Prompt Token Budget — 截断超额 section + 重排以利用 Prompt Cache
        from .prompt_budget_manager import PromptBudgetManager
        _budget_mgr = PromptBudgetManager()
        prompt_sections = _budget_mgr.apply_budget(prompt_sections)
        prompt_sections = _budget_mgr.reorder_for_cache(prompt_sections)

        prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
        logger.debug("Pipeline prompt length: %s chars", len(prompt_input))

        # ---- Literary 模式：加载精简 prompt ----
        if config.use_slim_prompt:
            slim_prompt = await self.prompt_service.get_prompt("writing_v3")
            if slim_prompt:
                writer_prompt = slim_prompt

        _mark_stage("build_generation_prompt", stage_started)
        await _emit_stage("build_generation_prompt", "完成上下文组装，开始写作")

        # ========== Literary 模式：场景级分步生成 ==========
        if config.enable_scene_by_scene:
            await _emit_stage("generate_scene_by_scene", "按场景分步生成中")
            stage_started = time.perf_counter()

            # 声纹样本（已在 prepare_context 阶段提前启动，此处仅 await）
            voice_samples_text = ""
            if _voice_samples_task is not None:
                voice_samples_text = await _voice_samples_task

            prompt_sections_data = {
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
                "voice_samples": voice_samples_text,
            }

            version = await self._generate_scene_by_scene(
                prompt_sections_data=prompt_sections_data,
                writer_prompt=writer_prompt,
                chapter_mission=chapter_mission,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                user_id=user_id,
                genre_profile=genre_profile,
                voice_samples_text=voice_samples_text,
            )
            versions = [version]
            _mark_stage("generate_scene_by_scene", stage_started)

            # ---- Literary 后处理：雕塑式重写（替代 multi-version review + optimizer） ----
            stage_started = time.perf_counter()
            best_content = version["content"]
            review_summaries: Dict[str, Any] = {}
            literary_profile = self._resolve_literary_postprocess_profile(
                config=config,
                chapter_mission=chapter_mission,
                target_word_count=chapter_target_word_count,
            )
            review_summaries["literary_profile"] = literary_profile

            if literary_profile["enable_prose_sculpting"]:
                from .prose_sculptor_service import ProseSculptorService
                sculptor = ProseSculptorService(self.llm_service)

                best_content, rhythm_report = await sculptor.sculpt_rhythm(
                    best_content, user_id=user_id, max_word_count=chapter_word_count_max,
                )
                review_summaries["rhythm_sculpting"] = rhythm_report

                best_content, density_report = await sculptor.sculpt_density(
                    best_content, user_id=user_id, max_word_count=chapter_word_count_max,
                )
                review_summaries["density_sculpting"] = density_report

            if literary_profile["enable_golden_paragraph"]:
                from .prose_sculptor_service import ProseSculptorService
                sculptor = ProseSculptorService(self.llm_service)
                best_content, golden_report = await sculptor.enhance_peak_moments(
                    best_content, user_id=user_id, chapter_mission=chapter_mission,
                )
                review_summaries["golden_paragraph"] = golden_report

            # 人味化：先规则修复（无 LLM），再视分数决定是否 LLM 修复
            if literary_profile["enable_humanization"]:
                try:
                    from .humanization_service import HumanizationService
                    h_service = HumanizationService(self.session, self.llm_service)
                    h_report = h_service.scan(best_content)
                    best_content = h_service.apply_rule_fixes(best_content, h_report)
                    h_report = h_service.scan(best_content)  # 规则修复后重扫
                    humanized = False
                    if h_report.score < config.humanization_threshold:
                        best_content = await h_service.humanize(
                            best_content, h_report, user_id=user_id,
                        )
                        humanized = True
                    review_summaries["humanization"] = {
                        "score": h_report.score,
                        "issues_count": len(h_report.issues),
                        "humanized": humanized,
                    }
                except Exception as e:
                    logger.warning("人味化检查失败: %s", e)

            best_content, enrichment_report = await self._run_enrichment(
                best_content,
                user_id=user_id,
                target_word_count=chapter_target_word_count,
                min_word_count=chapter_word_count_min,
                max_word_count=chapter_word_count_max,
            )
            if enrichment_report:
                review_summaries["enrichment"] = enrichment_report

            # 最终护栏
            guardrail_result = self.guardrails.check(
                generated_text=best_content,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                pov=chapter_mission.get("pov") if chapter_mission else None,
            )
            if not guardrail_result.passed:
                best_content = self.guardrails.apply_local_patches(best_content, guardrail_result)

            _mark_stage("literary_post_processing", stage_started)

            version["content"] = best_content
            version.setdefault("metadata", {})["review_summaries"] = review_summaries

            # 背景分析任务
            six_dimension_payload = None
            if enhanced_flow and config.enable_six_dimension:
                six_dimension_payload = {
                    "project_id": project_id,
                    "chapter_number": chapter_number,
                    "chapter_title": outline_title,
                    "chapter_content": best_content,
                    "chapter_plan": json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                    "previous_summary": history_context["previous_summary"],
                }

            async def _do_quality_detection_literary() -> None:
                recent_openings = [
                    ch["summary"][:200]
                    for ch in history_context.get("completed_chapters", [])
                    if ch.get("summary")
                ][-3:]
                quality_report = await self._run_quality_detection(
                    best_content,
                    chapter_number=chapter_number,
                    chapter_mission=chapter_mission,
                    previous_chapters_openings=recent_openings,
                    user_id=user_id,
                )
                review_summaries["quality_detection"] = quality_report

            stage_started = time.perf_counter()
            await _do_quality_detection_literary()
            _mark_stage("literary_readonly_analyses", stage_started)

            # 最终字数兜底：如果后处理导致超限，执行压缩
            if len(best_content) > chapter_word_count_max:
                logger.info("Literary最终字数超限 (%d > %d)，触发兜底压缩", len(best_content), chapter_word_count_max)
                best_content = await self._compress_overlength(best_content, target_max=chapter_word_count_max, user_id=user_id)
                version["content"] = best_content

            # 持久化
            contents = [version["content"]]
            metadata_list = [version.get("metadata")]
            stage_started = time.perf_counter()
            versions_models = await self.novel_service.replace_chapter_versions(chapter, contents, metadata_list)
            _mark_stage("persist_versions", stage_started)

            if six_dimension_payload and versions_models:
                best_version_id = versions_models[0].id
                six_dim_task = asyncio.create_task(
                    self._run_six_dimension_review_async(version_id=best_version_id, **six_dimension_payload)
                )
                self._background_tasks.add(six_dim_task)
                six_dim_task.add_done_callback(self._background_tasks.discard)

            # Literary 模式同样需要更新记忆层（与标准模式保持一致）
            # 使用后台任务避免阻塞章节返回
            if config.enable_memory:
                memory_task = asyncio.create_task(
                    self._run_memory_update_async(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_content=best_content,
                        character_names=introduced_characters,
                        user_id=user_id,
                    )
                )
                self._background_tasks.add(memory_task)
                memory_task.add_done_callback(self._background_tasks.discard)

            variants = [{"index": 0, "version_id": versions_models[0].id, "content": version["content"], "metadata": version.get("metadata")}]
            stage_timings_ms["total_pipeline"] = int((time.perf_counter() - total_started) * 1000)

            # 更新进度：章节生成完成
            await progress_service.update_stage(
                project_id, chapter_number,
                WritingStage.MAIN_WRITING,
                StageStatus.COMPLETED,
                progress=100,
                message="章节生成完成"
            )
            await progress_service.complete(project_id, chapter_number, success=True)

            return {
                "project_id": project_id,
                "chapter_number": chapter_number,
                "preset": config.preset,
                "best_version_index": 0,
                "variants": variants,
                "review_summaries": review_summaries,
                "debug_metadata": {
                    "version_count": 1,
                    "mode": "literary_scene_by_scene",
                    "stages": self._build_stage_flags(config),
                    "retrieval_stats": rag_stats,
                    "stage_timings_ms": stage_timings_ms,
                },
            }

        if config.enable_fast_path:
            await _emit_stage("generate_fast_version", "快速模式：生成正文中")

            async def _stream_fast_text_delta(delta: str) -> None:
                await _emit_stream(
                    "text_delta",
                    {
                        "delta": delta,
                        "stage": "generate_fast_version",
                        "chapter_number": chapter_number,
                    },
                )

            stage_started = time.perf_counter()
            version = await self._generate_single_version(
                index=0,
                prompt_input=prompt_input,
                writer_prompt=writer_prompt,
                style_hint=None,
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
                target_word_count=chapter_target_word_count,
                max_word_count=chapter_word_count_max,
                genre_profile=genre_profile,
                disable_guardrail_rewrite=config.disable_guardrail_rewrite,
                stream_callback=_stream_fast_text_delta if stream_handler else None,
            )
            _mark_stage("generate_fast_version", stage_started)

            best_content = version.get("content", "")
            review_summaries: Dict[str, Any] = {}

            if config.enable_lightweight_humanization:
                stage_started = time.perf_counter()
                try:
                    from .humanization_service import HumanizationService
                    h_service = HumanizationService(self.session, self.llm_service)
                    h_report = h_service.scan(best_content)
                    best_content = h_service.apply_rule_fixes(best_content, h_report)
                    review_summaries["lightweight_humanization"] = {
                        "score": h_report.score,
                        "issues_count": len(h_report.issues),
                    }
                except Exception as e:
                    logger.warning("Fast 规则人味化失败（不影响生成）: %s", e)
                    review_summaries["lightweight_humanization"] = {"error": str(e)}
                _mark_stage("fast_lightweight_humanization", stage_started)

            if config.enable_polish:
                stage_started = time.perf_counter()
                best_content, polish_report = await self._run_polish(
                    best_content,
                    user_id=user_id,
                    max_word_count=chapter_word_count_max,
                )
                review_summaries["polish"] = polish_report
                _mark_stage("fast_optional_polish", stage_started)

            if len(best_content) > chapter_word_count_max:
                logger.info(
                    "Fast模式最终字数超限 (%d > %d)，触发兜底压缩",
                    len(best_content),
                    chapter_word_count_max,
                )
                best_content = await self._compress_overlength(
                    best_content,
                    target_max=chapter_word_count_max,
                    user_id=user_id,
                )

            version["content"] = best_content
            review_summaries["quality_detection"] = {"status": "scheduled_async"}
            if config.enable_anti_hallucination:
                review_summaries["anti_hallucination"] = {
                    "status": "scheduled_async",
                    "mode": "local_registry" if config.use_local_anti_hallucination else "llm",
                }
            version.setdefault("metadata", {})["review_summaries"] = review_summaries

            stage_started = time.perf_counter()
            await _emit_stage("persist_versions", "写入章节版本中")
            versions_models = await self.novel_service.replace_chapter_versions(
                chapter,
                [version["content"]],
                [version.get("metadata")],
            )
            _mark_stage("persist_versions", stage_started)

            _stage_b_params: Optional[Dict[str, Any]] = {
                "analysis_snapshot": best_content,
                "project_id": project_id,
                "chapter_number": chapter_number,
                "chapter_mission": chapter_mission,
                "previous_summary": history_context["previous_summary"],
                "completed_chapters": history_context.get("completed_chapters", []),
                "enable_reader_sim": False,
                "enable_anti_hallucination": config.enable_anti_hallucination,
                "anti_hallucination_local_only": config.use_local_anti_hallucination,
                "user_id": user_id,
            }

            if _stage_b_params and versions_models:
                stage_b_bg_task = asyncio.create_task(
                    self._run_stage_b_analyses_async(
                        version_id=versions_models[0].id,
                        **_stage_b_params,
                    )
                )
                self._background_tasks.add(stage_b_bg_task)
                stage_b_bg_task.add_done_callback(self._background_tasks.discard)

            if config.enable_memory:
                memory_task = asyncio.create_task(
                    self._run_memory_update_async(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_content=best_content,
                        character_names=introduced_characters,
                        user_id=user_id,
                    )
                )
                self._background_tasks.add(memory_task)
                memory_task.add_done_callback(self._background_tasks.discard)

            variants = [
                {
                    "index": 0,
                    "version_id": versions_models[0].id,
                    "content": version["content"],
                    "metadata": version.get("metadata"),
                }
            ]
            stage_timings_ms["total_pipeline"] = int((time.perf_counter() - total_started) * 1000)
            await _emit_stage("completed", "章节生成完成")
            return {
                "project_id": project_id,
                "chapter_number": chapter_number,
                "preset": config.preset,
                "best_version_index": 0,
                "variants": variants,
                "review_summaries": review_summaries,
                "debug_metadata": {
                    "version_count": 1,
                    "mode": "fast_single_pass",
                    "stages": self._build_stage_flags(config),
                    "retrieval_stats": rag_stats,
                    "stage_timings_ms": stage_timings_ms,
                },
            }

        # ========== 标准模式：多版本并行生成 ==========
        await _emit_stage("generate_versions", "多版本生成中")
        version_count = config.version_count
        version_style_hints = self._resolve_style_hints(enhanced_context, version_count)

        stage_started = time.perf_counter()
        versions: List[Dict[str, Any]] = []
        version_tasks = []
        for idx in range(version_count):
            style_hint = version_style_hints[idx] if idx < len(version_style_hints) else None
            version_tasks.append(
                self._generate_single_version(
                    index=idx,
                    prompt_input=prompt_input,
                    writer_prompt=writer_prompt,
                    style_hint=style_hint,
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
                    target_word_count=chapter_target_word_count,
                    max_word_count=chapter_word_count_max,
                    genre_profile=genre_profile,
                    disable_guardrail_rewrite=config.disable_guardrail_rewrite,
                )
            )
        versions = list(await asyncio.gather(*version_tasks))
        _mark_stage("generate_versions", stage_started)

        stage_started = time.perf_counter()
        best_version_index, ai_review_result = await self._run_ai_review(
            versions=versions,
            chapter_mission=chapter_mission,
            user_id=user_id,
        )
        _mark_stage("ai_review", stage_started)

        review_summaries: Dict[str, Any] = {}
        six_dimension_payload: Optional[Dict[str, Any]] = None
        _stage_b_params: Optional[Dict[str, Any]] = None
        if ai_review_result:
            review_summaries["ai_review"] = ai_review_result

        if versions:
            best_version_index = max(0, min(best_version_index, len(versions) - 1))
        else:
            best_version_index = 0

        if versions:
            best_version = versions[best_version_index]
            best_content = best_version["content"]

            # ========== 阶段 A：后处理步骤（优化版：部分并行）==========
            stage_started = time.perf_counter()

            # ---- A.1 合并修订：revision + self_critique → 一次 LLM 调用 ----
            _has_review_feedback = ai_review_result and (ai_review_result.get("flaws") or ai_review_result.get("suggestions"))
            if _has_review_feedback or config.enable_self_critique:
                best_content, combined_report = await self._run_combined_revision(
                    best_content,
                    critical_flaws=(ai_review_result.get("flaws") or []) if ai_review_result else [],
                    refinement_suggestions=(ai_review_result.get("suggestions") or "") if ai_review_result else "",
                    enable_self_critique=config.enable_self_critique,
                    chapter_mission=chapter_mission,
                    user_id=user_id,
                    context={
                        "character_profiles": json.dumps(writer_blueprint.get("characters", []), ensure_ascii=False),
                        "previous_summary": history_context["previous_summary"],
                    },
                    max_word_count=chapter_word_count_max,
                )
                review_summaries["combined_revision"] = combined_report

            # ---- A.2 并行：一致性检查 + 人味化扫描 ----
            _consistency_enabled = config.enable_consistency
            _humanization_enabled = config.enable_humanization

            if _consistency_enabled and _humanization_enabled:
                # 并行执行：一致性检查（LLM）+ 人味化扫描（本地，无 LLM）
                async def _do_consistency():
                    return await self._run_consistency_check(
                        project_id=project_id,
                        chapter_text=best_content,
                        user_id=user_id,
                    )

                async def _do_humanization_scan():
                    try:
                        from .humanization_service import HumanizationService
                        h_service = HumanizationService(self.session, self.llm_service)
                        return h_service, h_service.scan(best_content)
                    except Exception as e:
                        logger.warning("人味化扫描失败（不影响生成）: %s", e)
                        return None, None

                (consistency_content, consistency_report), (h_service, h_report) = await asyncio.gather(
                    _do_consistency(),
                    _do_humanization_scan(),
                )
                best_content = consistency_content
                review_summaries["consistency"] = consistency_report

                # 人味化 LLM 修复（基于一致性修复后的内容）
                if h_service and h_report:
                    humanized = False
                    if h_report.score < config.humanization_threshold:
                        logger.info(
                            "人味分数 %d < 阈值 %d，触发 LLM 修复",
                            h_report.score, config.humanization_threshold,
                        )
                        # 重新扫描一致性修复后的内容
                        h_report = h_service.scan(best_content)
                        if h_report.score < config.humanization_threshold:
                            best_content = await h_service.humanize(
                                best_content, h_report, user_id=user_id,
                            )
                            humanized = True
                    review_summaries["humanization"] = {
                        "score": h_report.score,
                        "issues_count": len(h_report.issues),
                        "humanized": humanized,
                        "details": h_report.to_dict(),
                    }
            else:
                if _consistency_enabled:
                    best_content, consistency_report = await self._run_consistency_check(
                        project_id=project_id,
                        chapter_text=best_content,
                        user_id=user_id,
                    )
                    review_summaries["consistency"] = consistency_report

                if _humanization_enabled:
                    try:
                        from .humanization_service import HumanizationService
                        h_service = HumanizationService(self.session, self.llm_service)
                        h_report = h_service.scan(best_content)
                        humanized = False
                        if h_report.score < config.humanization_threshold:
                            logger.info(
                                "人味分数 %d < 阈值 %d，触发 LLM 修复",
                                h_report.score, config.humanization_threshold,
                            )
                            best_content = await h_service.humanize(
                                best_content, h_report, user_id=user_id,
                            )
                            humanized = True
                        review_summaries["humanization"] = {
                            "score": h_report.score,
                            "issues_count": len(h_report.issues),
                            "humanized": humanized,
                            "details": h_report.to_dict(),
                        }
                    except Exception as e:
                        logger.warning("人味化检查失败（不影响生成）: %s", e)
                        review_summaries["humanization"] = {"error": str(e)}

            # ---- Stage B 改为后台异步：捕获快照，后续在 persist 后启动后台任务 ----
            _analysis_snapshot = best_content
            _stage_b_params = {
                "analysis_snapshot": _analysis_snapshot,
                "project_id": project_id,
                "chapter_number": chapter_number,
                "chapter_mission": chapter_mission,
                "previous_summary": history_context["previous_summary"],
                "completed_chapters": history_context.get("completed_chapters", []),
                "enable_reader_sim": config.enable_reader_sim,
                "enable_anti_hallucination": config.enable_anti_hallucination,
                "anti_hallucination_local_only": config.use_local_anti_hallucination,
                "user_id": user_id,
            }
            if config.enable_reader_sim:
                review_summaries["reader_simulator"] = {"status": "scheduled_async"}
            if config.enable_anti_hallucination:
                review_summaries["anti_hallucination"] = {"status": "scheduled_async"}
            review_summaries["quality_detection"] = {"status": "scheduled_async"}

            # ---- A.3 optimizer(+polish+density) / enrichment（与 Stage B 并行执行） ----
            _optimizer_enabled = config.enable_optimizer
            # P4 优化: optimizer 启用时跳过 enrichment（结果会被丢弃）
            _enrichment_enabled = config.enable_enrichment and not _optimizer_enabled
            _polish_only = config.enable_polish and not config.enable_optimizer
            if _optimizer_enabled:
                merge_polish = config.enable_polish
                # 优化项2: 当密度压缩启用且字数 >= 上限90% 时，合并到 optimizer 一次 LLM 调用
                merge_density = (
                    config.enable_density_compression
                    and chapter_word_count_max
                    and len(best_content) >= chapter_word_count_max * 0.90
                )
                best_content, optimizer_report = await self._run_optimizer(
                    best_content, user_id=user_id, include_polish=merge_polish,
                    include_density=merge_density,
                    max_word_count=chapter_word_count_max,
                )
                review_summaries["optimizer"] = optimizer_report
                if merge_polish:
                    review_summaries["polish"] = {"applied": True, "merged_into_optimizer": True}
                if merge_density:
                    review_summaries["density_compression"] = {"applied": True, "merged_into_optimizer": True}

            if _polish_only:
                best_content, polish_report = await self._run_polish(best_content, user_id=user_id, max_word_count=chapter_word_count_max)
                review_summaries["polish"] = polish_report

            if _enrichment_enabled:
                best_content, enrichment_report = await self._run_enrichment(
                    best_content,
                    user_id=user_id,
                    target_word_count=chapter_target_word_count,
                    min_word_count=chapter_word_count_min,
                    max_word_count=chapter_word_count_max,
                )
                if enrichment_report:
                    review_summaries["enrichment"] = enrichment_report

            # 密度压缩：仅在未合并到 optimizer 时独立执行
            if config.enable_density_compression and not (_optimizer_enabled and review_summaries.get("density_compression", {}).get("merged_into_optimizer")):
                _current_len = len(best_content)
                if chapter_word_count_max and _current_len < chapter_word_count_max * 0.90:
                    logger.info(
                        "章节字数低于上限90%% (%d < %d)，跳过密度压缩",
                        _current_len, int(chapter_word_count_max * 0.90),
                    )
                    review_summaries["density_compression"] = {"applied": False, "reason": "below_90pct_max"}
                else:
                    best_content, density_report = await self._run_density_compression(best_content, user_id=user_id, max_word_count=chapter_word_count_max)
                    review_summaries["density_compression"] = density_report
            _mark_stage("stage_a_post_processing", stage_started)

            # ========== six_dimension 使用最终内容 ==========
            if enhanced_flow and config.enable_six_dimension:
                six_dimension_payload = {
                    "project_id": project_id,
                    "chapter_number": chapter_number,
                    "chapter_title": outline_title,
                    "chapter_content": best_content,
                    "chapter_plan": json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                    "previous_summary": history_context["previous_summary"],
                }
                review_summaries["enhanced_review"] = {"status": "scheduled"}

            # 优化项5: 最终护栏检查（在所有后处理完成后统一执行）
            _best_guardrail_meta = best_version.get("metadata", {}).get("guardrail", {})
            if _best_guardrail_meta.get("deferred_llm_rewrite"):
                final_guardrail = self.guardrails.check(
                    generated_text=best_content,
                    forbidden_characters=forbidden_characters,
                    allowed_new_characters=allowed_new_characters,
                    pov=chapter_mission.get("pov") if chapter_mission else None,
                )
                if not final_guardrail.passed:
                    best_content = self.guardrails.apply_local_patches(best_content, final_guardrail)
                    recheck = self.guardrails.check(
                        generated_text=best_content,
                        forbidden_characters=forbidden_characters,
                        allowed_new_characters=allowed_new_characters,
                        pov=chapter_mission.get("pov") if chapter_mission else None,
                    )
                    if not recheck.passed:
                        violations_text = self.guardrails.format_violations_for_rewrite(recheck)
                        best_content = await _shared_rewrite_with_guardrails(
                            self.llm_service,
                            self.prompt_service,
                            original_text=best_content,
                            chapter_mission=chapter_mission,
                            violations_text=violations_text,
                            user_id=user_id,
                        )
                    _best_guardrail_meta["final_guardrail_applied"] = True
                else:
                    # 后处理已自然修复了护栏违规，无需 LLM 重写
                    _best_guardrail_meta["deferred_llm_rewrite"] = False
                    _best_guardrail_meta["resolved_by_postprocess"] = True

            best_version["content"] = best_content
            best_version.setdefault("metadata", {})["review_summaries"] = review_summaries

        # 最终字数兜底（仅在 versions 非空时执行，best_content 在 if versions: 分支中定义）
        if versions:
            if len(best_content) > chapter_word_count_max:
                logger.info("标准模式最终字数超限 (%d > %d)，触发兜底压缩", len(best_content), chapter_word_count_max)
                best_content = await self._compress_overlength(best_content, target_max=chapter_word_count_max, user_id=user_id)
                best_version["content"] = best_content

        contents = [v.get("content", "") for v in versions]
        metadata = [v.get("metadata") for v in versions]
        stage_started = time.perf_counter()
        versions_models = await self.novel_service.replace_chapter_versions(chapter, contents, metadata)
        _mark_stage("persist_versions", stage_started)

        stage_started = time.perf_counter()
        if six_dimension_payload and 0 <= best_version_index < len(versions_models):
            best_version_id = versions_models[best_version_index].id
            six_dimension_task = asyncio.create_task(
                self._run_six_dimension_review_async(
                    version_id=best_version_id,
                    **six_dimension_payload,
                )
            )
            self._background_tasks.add(six_dimension_task)
            six_dimension_task.add_done_callback(self._background_tasks.discard)
        _mark_stage("schedule_async_six_dimension", stage_started)

        # Stage B 只读分析：后台异步执行，不阻塞响应返回
        if _stage_b_params and 0 <= best_version_index < len(versions_models):
            stage_b_version_id = versions_models[best_version_index].id
            stage_b_bg_task = asyncio.create_task(
                self._run_stage_b_analyses_async(
                    version_id=stage_b_version_id,
                    **_stage_b_params,
                )
            )
            self._background_tasks.add(stage_b_bg_task)
            stage_b_bg_task.add_done_callback(self._background_tasks.discard)

        # 使用后台任务更新记忆层，避免阻塞章节返回（节省 30-60s）
        if config.enable_memory:
            memory_task = asyncio.create_task(
                self._run_memory_update_async(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_content=best_content,
                    character_names=introduced_characters,
                    user_id=user_id,
                )
            )
            self._background_tasks.add(memory_task)
            memory_task.add_done_callback(self._background_tasks.discard)

        variants = []
        for idx, version_model in enumerate(versions_models):
            variant = {
                "index": idx,
                "version_id": version_model.id,
                "content": versions[idx].get("content", ""),
                "metadata": versions[idx].get("metadata"),
            }
            variants.append(variant)

        stage_timings_ms["total_pipeline"] = int((time.perf_counter() - total_started) * 1000)

        # 更新进度：章节生成完成
        await progress_service.update_stage(
            project_id, chapter_number,
            WritingStage.MAIN_WRITING,
            StageStatus.COMPLETED,
            progress=100,
            message=f"生成{version_count}个版本"
        )
        await progress_service.complete(project_id, chapter_number, success=True)

        return {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "preset": config.preset,
            "best_version_index": best_version_index,
            "variants": variants,
            "review_summaries": review_summaries,
            "debug_metadata": {
                "version_count": version_count,
                "stages": self._build_stage_flags(config),
                "retrieval_stats": rag_stats,
                "stage_timings_ms": stage_timings_ms,
            },
        }

    async def _run_stage_b_analyses_async(
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
        """后台异步执行 Stage B 只读分析（reader_sim / anti_hallucination / quality_detection），使用独立 DB session。"""
        try:
            async with AsyncSessionLocal() as bg_session:
                try:
                    bg_llm = LLMService(bg_session)
                    bg_prompt = PromptService(bg_session)
                    results: Dict[str, Any] = {}

                    async def _bg_reader_sim() -> None:
                        if not enable_reader_sim:
                            return
                        try:
                            from .reader_simulator_service import ReaderSimulatorService, ReaderType
                            service = ReaderSimulatorService(bg_session, bg_llm, bg_prompt)
                            feedback = await service.simulate_reading_experience(
                                chapter_content=analysis_snapshot,
                                chapter_number=chapter_number,
                                reader_types=[ReaderType.THRILL_SEEKER, ReaderType.CRITIC, ReaderType.CASUAL],
                                previous_summary=previous_summary,
                                user_id=user_id,
                            )
                            results["reader_simulator"] = feedback
                        except Exception as e:
                            logger.warning("后台读者模拟失败: %s", e)
                            results["reader_simulator"] = {"error": str(e)}

                    async def _bg_anti_hallucination() -> None:
                        if not enable_anti_hallucination:
                            return
                        try:
                            if anti_hallucination_local_only:
                                from .entity_registry_service import EntityRegistryService

                                entity_service = EntityRegistryService(bg_session)
                                entities = await entity_service.get_all_entities(project_id)
                                known_names = set()
                                for entity in entities:
                                    known_names.add(entity.canonical_name)
                                    for alias in (entity.aliases or []):
                                        known_names.add(alias.alias)

                                unregistered = await entity_service.detect_unregistered_names(
                                    project_id=project_id,
                                    text=analysis_snapshot,
                                    known_names=known_names,
                                )
                                warnings = [item for item in unregistered if item.get("occurrences", 0) >= 2][:8]
                                criticals = [item for item in unregistered if item.get("occurrences", 0) >= 5][:3]
                                report_lines = []
                                for item in warnings:
                                    report_lines.append(
                                        f"- 未注册名称「{item.get('name', '')}」出现 {item.get('occurrences', 0)} 次"
                                    )
                                results["anti_hallucination"] = {
                                    "mode": "local_registry",
                                    "passed": len(criticals) == 0,
                                    "registered_count": 0,
                                    "warning_count": len(warnings),
                                    "critical_count": len(criticals),
                                    "report": "\n".join(report_lines) if report_lines else "本地实体检测未发现高频未注册名称",
                                    "unregistered_top": warnings,
                                }
                            else:
                                from .anti_hallucination_service import AntiHallucinationService

                                ah_service = AntiHallucinationService(bg_session, bg_llm)
                                ah_report = await ah_service.check_chapter(
                                    project_id=project_id,
                                    chapter_number=chapter_number,
                                    chapter_text=analysis_snapshot,
                                    user_id=user_id,
                                )
                                results["anti_hallucination"] = {
                                    "mode": "llm",
                                    "passed": ah_report.passed,
                                    "registered_count": ah_report.registered_count,
                                    "warning_count": ah_report.warning_count,
                                    "critical_count": ah_report.critical_count,
                                    "report": AntiHallucinationService.format_report_for_review(ah_report),
                                }
                        except Exception as e:
                            logger.warning("后台反幻觉检查失败: %s", e)
                            results["anti_hallucination"] = {"error": str(e)}

                    async def _bg_quality_detection() -> None:
                        try:
                            recent_openings = [
                                ch["summary"][:200]
                                for ch in completed_chapters
                                if ch.get("summary")
                            ][-3:]
                            opening_300 = analysis_snapshot[:300] if len(analysis_snapshot) > 300 else analysis_snapshot
                            ending_300 = analysis_snapshot[-300:] if len(analysis_snapshot) > 300 else analysis_snapshot

                            recent_patterns = ""
                            if recent_openings:
                                recent_patterns = "\n".join(
                                    f"第{i+1}个近期章节开头：{op[:200]}"
                                    for i, op in enumerate(recent_openings[-3:])
                                )

                            expected_beat = ""
                            if chapter_mission:
                                expected_beat = chapter_mission.get("macro_beat_description", "")
                                sat_type = chapter_mission.get("satisfaction_design", {}).get("type", "")
                                if sat_type:
                                    expected_beat += f"（爽感类型：{sat_type}）"

                            detection_prompt = f"""你是一位资深网文质量分析师。请分析以下章节的三个维度，输出JSON。\r
\r
## 分析维度\r
\r
### 1. 爽点密度\r
检查本章是否有足够的张力/冲突/反转/情绪高潮时刻。\r
- coolpoint_score (0-10)：爽点密度评分\r
- coolpoint_moments：列出识别到的爽点/张力时刻（最多5个，每个一句话描述）\r
- coolpoint_issue：如果评分<6，指出具体问题\r
\r
### 2. 模式重复\r
对比本章开头/结尾与近期章节是否存在套路化重复。\r
- repetition_score (0-10)：独特性评分（10=完全独特，0=严重套路化）\r
- repetition_issues：发现的重复模式（如"连续3章都以对话开头"、"结尾都用身体反应收束"）\r
- within_chapter_repetition：章节内部的句式/词汇重复\r
\r
### 3. 阶段性胜利 (Milestone Victory)\r
判断本章是否包含"改变主角地位、能力层级或势力格局的决定性事件"。\r
- milestone_victory_detected (true/false)：是否存在阶段性胜利\r
- milestone_description：如果存在，一句话描述该阶段性胜利的内容\r
\r
[本章开头300字]\r
{opening_300}\r
\r
[本章结尾300字]\r
{ending_300}\r
\r
[本章预期]\r
{expected_beat or "无特定预期"}\r
\r
[近期章节开头对比]\r
{recent_patterns or "无（这是前几章）"}\r
\r
输出严格JSON格式：\r
{{"coolpoint_score": 0, "coolpoint_moments": [], "coolpoint_issue": "", "repetition_score": 0, "repetition_issues": [], "within_chapter_repetition": [], "milestone_victory_detected": false, "milestone_description": ""}}"""

                            response = await bg_llm.get_llm_response(
                                system_prompt="你是一位擅长量化分析网文质量的编辑。只输出JSON，不要其他内容。",
                                conversation_history=[{"role": "user", "content": detection_prompt}],
                                temperature=0.2,
                                user_id=user_id,
                                timeout=60.0,
                            )
                            cleaned = remove_think_tags(response)
                            normalized = unwrap_markdown_json(cleaned or response)
                            try:
                                result = json.loads(normalized)
                            except json.JSONDecodeError:
                                result = json.loads(repair_json(normalized))
                            results["quality_detection"] = result
                        except Exception as exc:
                            logger.warning("后台质量检测失败: %s", exc)
                            results["quality_detection"] = {"error": str(exc), "coolpoint_score": -1, "repetition_score": -1}

                    await asyncio.gather(
                        _bg_reader_sim(),
                        _bg_anti_hallucination(),
                        _bg_quality_detection(),
                    )

                    if results:
                        db_result = await bg_session.execute(
                            select(ChapterVersion).where(ChapterVersion.id == version_id)
                        )
                        version = db_result.scalars().first()
                        if version:
                            metadata = dict(version.metadata_ or {})
                            review_summaries = dict(metadata.get("review_summaries") or {})
                            review_summaries.update(results)
                            metadata["review_summaries"] = review_summaries
                            version.metadata_ = metadata
                            await bg_session.commit()
                            logger.info(
                                "后台 Stage B 分析完成 project=%s chapter=%s version_id=%s keys=%s",
                                project_id, chapter_number, version_id, list(results.keys()),
                            )
                        else:
                            logger.warning(
                                "后台 Stage B 落库失败：版本不存在 version_id=%s",
                                version_id,
                            )
                except Exception:
                    await bg_session.rollback()
                    raise
        except Exception:
            logger.exception(
                "后台 Stage B 分析失败 project=%s chapter=%s version_id=%s",
                project_id, chapter_number, version_id,
            )

    async def _run_six_dimension_review_async(
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
        try:
            async with AsyncSessionLocal() as background_session:
                try:
                    llm_service = LLMService(background_session)
                    prompt_service = PromptService(background_session)
                    enhanced_flow = EnhancedWritingFlow(background_session, llm_service, prompt_service)
                    result = await enhanced_flow.post_generation_review(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_title=chapter_title,
                        chapter_content=chapter_content,
                        chapter_plan=chapter_plan,
                        previous_summary=previous_summary,
                    )

                    db_result = await background_session.execute(
                        select(ChapterVersion).where(ChapterVersion.id == version_id)
                    )
                    version = db_result.scalars().first()
                    if not version:
                        logger.warning(
                            "异步六维评审落库失败：版本不存在 project=%s chapter=%s version_id=%s",
                            project_id,
                            chapter_number,
                            version_id,
                        )
                        return

                    metadata = dict(version.metadata_ or {})
                    review_summaries = dict(metadata.get("review_summaries") or {})
                    review_summaries["enhanced_review"] = result
                    metadata["review_summaries"] = review_summaries
                    version.metadata_ = metadata
                    await background_session.commit()
                except Exception:
                    await background_session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步六维评审失败 project=%s chapter=%s version_id=%s",
                project_id,
                chapter_number,
                version_id,
            )

    async def _run_memory_update_async(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int,
    ) -> None:
        """后台异步执行记忆层更新，使用独立 DB session 避免影响主流程。"""
        try:
            async with AsyncSessionLocal() as background_session:
                try:
                    llm_service = LLMService(background_session)
                    prompt_service = PromptService(background_session)
                    from ..services.memory_layer_service import MemoryLayerService
                    memory_layer = MemoryLayerService(
                        background_session, llm_service, prompt_service
                    )
                    results = await memory_layer.update_memory_after_chapter(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_content=chapter_content,
                        character_names=character_names,
                        user_id=user_id,
                    )
                    logger.info(
                        "异步记忆层更新完成 project=%s chapter=%s results=%s",
                        project_id, chapter_number, results,
                    )
                except Exception:
                    await background_session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步记忆层更新失败 project=%s chapter=%s",
                project_id,
                chapter_number,
            )

    async def _resolve_config(self, flow_config: Optional[Dict[str, Any]]) -> PipelineConfig:
        flow_config = flow_config or {}
        preset = flow_config.get("preset", "basic")

        # 全局快速模式开关：当 WRITER_FAST_MODE=true 且前端未指定 literary 时，强制使用 fast preset
        if getattr(settings, "writer_fast_mode", False) and preset not in ("literary",):
            preset = "fast"

        config = PipelineConfig(preset=preset)
        config.version_count = await self._resolve_version_count(flow_config.get("versions"))
        config.literary_adaptive_postprocess = bool(
            getattr(settings, "writer_literary_adaptive_postprocess", True)
        )

        # 从全局配置读取新功能默认值
        config.rag_retrieval_mode = getattr(settings, "rag_retrieval_mode", "vector")
        config.pacing_model = getattr(settings, "pacing_model", "default")

        # 从全局配置读取人味化默认值
        if getattr(settings, "enable_humanization", True):
            config.enable_humanization = True
            config.humanization_threshold = getattr(settings, "humanization_threshold", 70)
        if getattr(settings, "enable_author_fingerprint", True):
            config.enable_fingerprint = True

        if preset in ("enhanced", "ultimate", "platinum"):
            config.enable_constitution = True
            config.enable_persona = True
            config.enable_foreshadowing = True
            config.enable_faction = True
            config.rag_mode = settings.rag_default_mode
            # enhanced+ 预设启用反幻觉
            if getattr(settings, "enable_entity_registry", True):
                config.enable_anti_hallucination = True

        if preset == "enhanced":
            config.enable_six_dimension = True
            config.enable_enrichment = True
            config.enable_polish = True

        if preset == "ultimate":
            config.enable_memory = True
            config.enable_six_dimension = True
            config.enable_consistency = True
            config.enable_enrichment = True
            config.enable_polish = True

        if preset == "platinum":
            config.enable_memory = True
            config.enable_six_dimension = True
            config.enable_self_critique = True
            config.enable_reader_sim = True
            config.enable_consistency = True
            config.enable_enrichment = True
            config.enable_polish = True

        if preset == "literary":
            config.version_count = 1
            config.enable_rag = True
            config.rag_mode = settings.rag_default_mode
            config.enable_constitution = True
            config.enable_persona = True
            config.enable_foreshadowing = True
            config.enable_faction = True
            config.enable_memory = True
            config.enable_humanization = True
            config.enable_fingerprint = True
            config.enable_mission_brief = True
            config.enable_scene_by_scene = True
            config.enable_prose_sculpting = True
            config.enable_golden_paragraph = True
            config.enable_reference_prose = True
            config.enable_voice_samples = True
            config.enable_narrative_variety = True
            config.use_slim_prompt = True
            if getattr(settings, "enable_entity_registry", True):
                config.enable_anti_hallucination = True

        if preset == "basic":
            config.enable_rag = True
            # basic 模式缺少 AI Review 选优机制，多版本无实际收益
            config.version_count = 1

        if preset == "fast":
            config.version_count = 1
            config.enable_fast_path = True
            config.enable_rag = True
            config.rag_mode = "simple"
            config.enable_constitution = False
            config.enable_persona = False
            config.enable_foreshadowing = False
            config.enable_faction = False
            config.enable_memory = False
            config.enable_humanization = False
            config.enable_lightweight_humanization = True  # fast：规则级去 AI 味，无 LLM
            config.enable_fingerprint = False
            config.enable_mission_brief = False
            config.enable_scene_by_scene = False
            config.enable_prose_sculpting = False
            config.enable_golden_paragraph = False
            config.enable_reference_prose = False
            config.enable_voice_samples = False
            config.enable_narrative_variety = False
            config.use_slim_prompt = False
            config.enable_six_dimension = False
            config.enable_self_critique = False
            config.enable_reader_sim = False
            config.enable_consistency = False
            config.enable_optimizer = False
            config.enable_enrichment = False
            config.enable_density_compression = False
            config.enable_preview = False
            config.disable_guardrail_rewrite = True
            config.skip_history_summary_backfill = True
            config.use_local_anti_hallucination = True
            config.enable_anti_hallucination = bool(getattr(settings, "enable_entity_registry", True))

        # Ultra fast mode: 启用快速路径 + 跳过所有后处理，达到最短耗时
        if getattr(settings, "writer_ultra_fast_mode", False):
            config.version_count = 1
            config.enable_fast_path = True
            config.enable_scene_by_scene = False
            config.enable_self_critique = False
            config.enable_consistency = False
            config.enable_humanization = False
            config.enable_lightweight_humanization = False
            config.enable_optimizer = False
            config.enable_enrichment = False
            config.enable_polish = False
            config.enable_reader_sim = False
            config.enable_anti_hallucination = False
            config.enable_density_compression = False
            config.enable_six_dimension = False
            config.enable_fingerprint = False
            config.enable_mission_brief = False
            config.enable_narrative_variety = False
            config.enable_reference_prose = False
            config.enable_voice_samples = False
            config.enable_prose_sculpting = False
            config.enable_golden_paragraph = False
            config.enable_constitution = False
            config.enable_persona = False
            config.enable_foreshadowing = False
            config.enable_faction = False
            config.enable_memory = False
            config.disable_guardrail_rewrite = True
            config.skip_history_summary_backfill = True
            config.use_local_anti_hallucination = True
            logger.info("Ultra fast mode: 已启用快速路径并跳过所有后处理步骤")

        for key in (
            "enable_preview",
            "enable_optimizer",
            "enable_consistency",
            "enable_enrichment",
            "async_finalize",
            "enable_rag",
            "enable_polish",
            "enable_mission_brief",
            "enable_density_compression",
            "enable_scene_by_scene",
            "enable_prose_sculpting",
            "enable_golden_paragraph",
            "enable_reference_prose",
            "enable_voice_samples",
            "enable_narrative_variety",
            "use_slim_prompt",
            "literary_adaptive_postprocess",
            "enable_fast_path",
            "enable_lightweight_humanization",
            "disable_guardrail_rewrite",
            "skip_history_summary_backfill",
            "use_local_anti_hallucination",
        ):
            if key in flow_config and flow_config[key] is not None:
                setattr(config, key, bool(flow_config[key]))

        if flow_config.get("rag_mode"):
            config.rag_mode = str(flow_config["rag_mode"])

        if flow_config.get("rag_retrieval_mode"):
            config.rag_retrieval_mode = str(flow_config["rag_retrieval_mode"])

        if flow_config.get("pacing_model"):
            config.pacing_model = str(flow_config["pacing_model"])

        return config

    async def _resolve_version_count(self, requested_count: Optional[int]) -> int:
        return await _shared_resolve_version_count(self.session, requested_count)

    async def _load_chapter_blueprint(
        self,
        project_id: str,
        chapter_number: int,
    ) -> Optional[ChapterBlueprint]:
        stmt = select(ChapterBlueprint).where(
            ChapterBlueprint.project_id == project_id,
            ChapterBlueprint.chapter_number == chapter_number,
        )

        try:
            result = await self.session.execute(stmt)
        except OperationalError as exc:
            repaired = await repair_schema_if_needed(exc)
            if not repaired:
                raise
            result = await self.session.execute(stmt)

        return result.scalars().first()

    @staticmethod
    def _extract_fast_keywords(text: Optional[str]) -> List[str]:
        if not text:
            return []
        import re

        tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", text)
        stop_words = {
            "本章",
            "章节",
            "当前",
            "相关",
            "内容",
            "剧情",
            "要求",
            "以及",
            "需要",
            "进行",
            "一个",
            "我们",
            "他们",
        }
        result: List[str] = []
        for token in tokens:
            cleaned = token.strip()
            if not cleaned or cleaned in stop_words:
                continue
            result.append(cleaned)
        return result

    def _build_fast_rag_queries(
        self,
        *,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        chapter_blueprint: Optional[ChapterBlueprint],
    ) -> List[str]:
        queries: List[str] = [outline_title, outline_summary]
        if writing_notes and writing_notes != "无额外写作指令":
            queries.append(writing_notes)

        keyword_pool: List[str] = []
        if chapter_blueprint:
            keyword_pool.extend(self._extract_fast_keywords(chapter_blueprint.chapter_focus))
            keyword_pool.extend(self._extract_fast_keywords(chapter_blueprint.brief_summary))
            keyword_pool.extend(self._extract_fast_keywords(chapter_blueprint.chapter_function))
            keyword_pool.extend(self._extract_fast_keywords(chapter_blueprint.suspense_type))
            keyword_pool.extend(self._extract_fast_keywords(chapter_blueprint.emotional_arc))
            constraints = chapter_blueprint.mission_constraints or {}
            if isinstance(constraints, dict):
                for value in constraints.get("must_include", [])[:6]:
                    keyword_pool.extend(self._extract_fast_keywords(str(value)))

        deduped_keywords = list(dict.fromkeys(keyword_pool))
        if deduped_keywords:
            queries.append(" ".join(deduped_keywords[:10]))

        return [item for item in queries if item][:4]

    def _build_fast_chapter_mission(
        self,
        *,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        chapter_blueprint: Optional[ChapterBlueprint],
    ) -> Dict[str, Any]:
        constraints = (
            dict(chapter_blueprint.mission_constraints or {})
            if chapter_blueprint and isinstance(chapter_blueprint.mission_constraints, dict)
            else {}
        )
        min_words, max_words, target_words = self._resolve_word_count_bounds()
        budget_cfg = constraints.get("word_budget") or {}
        word_budget = {
            "min": int(budget_cfg.get("min") or min_words),
            "target": int(budget_cfg.get("target") or target_words),
            "max": int(budget_cfg.get("max") or max_words),
            "total": int(budget_cfg.get("target") or target_words),
        }
        if word_budget["max"] < word_budget["min"]:
            word_budget["max"] = word_budget["min"]

        chapter_function = (
            (chapter_blueprint.chapter_function if chapter_blueprint else None)
            or "progression"
        )
        satisfaction_type = {
            "climax": "高潮爆发",
            "turning": "转折兑现",
            "revelation": "信息揭示",
            "resolution": "阶段收束",
            "interlude": "无（蓄力中）",
            "buildup": "无（蓄力中）",
            "progression": "推进成长",
        }.get(chapter_function, "推进成长")

        focus = (
            (chapter_blueprint.chapter_focus if chapter_blueprint else None)
            or (chapter_blueprint.brief_summary if chapter_blueprint else None)
            or outline_summary
            or outline_title
        )
        must_include = constraints.get("must_include") or []
        must_not_include = constraints.get("must_not_include") or []
        scene_list = constraints.get("scene_list") or []
        allowed_new_characters = constraints.get("allowed_new_characters") or []
        pov_character = constraints.get("pov_character")

        notes_block = ""
        if writing_notes and writing_notes != "无额外写作指令":
            notes_block = f"；用户指令：{writing_notes}"
        mission_summary = f"第{chapter_number}章核心任务：{focus}{notes_block}"

        return {
            "chapter_type": chapter_function,
            "macro_beat": chapter_function,
            "macro_beat_description": mission_summary,
            "satisfaction_design": {"type": satisfaction_type},
            "word_budget": word_budget,
            "scene_list": scene_list,
            "allowed_new_characters": allowed_new_characters,
            "must_include": must_include,
            "must_not_include": must_not_include,
            "pov": pov_character,
        }

    @staticmethod
    def _resolve_word_count_bounds() -> Tuple[int, int, int]:
        """解析章节字数上下限与目标字数，优先采用运行时配置。"""
        try:
            min_words = int(getattr(settings, "writer_chapter_word_count_min", CHAPTER_MIN_WORDS))
        except (TypeError, ValueError):
            min_words = CHAPTER_MIN_WORDS
        try:
            max_words = int(getattr(settings, "writer_chapter_word_count_max", CHAPTER_MAX_WORDS))
        except (TypeError, ValueError):
            max_words = CHAPTER_MAX_WORDS

        if min_words < 1:
            min_words = CHAPTER_MIN_WORDS
        if max_words < min_words:
            max_words = min_words

        target_words = min_words + (max_words - min_words) // 2
        return min_words, max_words, target_words

    @staticmethod
    def _resolve_style_hints(
        enhanced_context: Optional[Dict[str, Any]],
        version_count: int,
    ) -> List[str]:
        if enhanced_context and enhanced_context.get("version_style_hints"):
            hints = enhanced_context["version_style_hints"]
            if isinstance(hints, list) and hints:
                return hints[:version_count]
        return [
            "情绪更细腻，节奏更慢，多写内心戏和感官描写",
            "冲突更强，节奏更快，多写动作和对话",
            "悬念更重，多埋伏笔，结尾钩子更强",
        ][:version_count]

    @staticmethod
    def _resolve_pov_character(chapter_mission: Optional[dict]) -> Optional[str]:
        if not chapter_mission:
            return None
        return chapter_mission.get("pov") or chapter_mission.get("pov_character")

    @staticmethod
    def _resolve_temperature(chapter_mission: Optional[dict]) -> float:
        """根据章节类型动态选择生成温度。

        爽点章 0.85 / 刀子章 0.75 / 蓄力章 0.65 / 过渡章 0.60 / 默认 0.75
        """
        if not chapter_mission:
            return 0.75

        macro_beat = (chapter_mission.get("macro_beat") or "").lower()
        sat_type = (chapter_mission.get("satisfaction_design") or {}).get("type", "")

        # 爽点章：包含爽感设计或明确的高潮/爆发节拍
        if sat_type and sat_type != "无（蓄力中）":
            return 0.85
        for kw in ("高潮", "爆发", "反转", "逆袭", "决战", "爽"):
            if kw in macro_beat:
                return 0.85

        # 刀子章：虐心、离别、牺牲
        for kw in ("虐", "刀", "离别", "牺牲", "背叛", "死亡", "失去"):
            if kw in macro_beat:
                return 0.75

        # 蓄力章：铺垫、布局、积蓄
        for kw in ("蓄力", "铺垫", "布局", "积蓄", "准备", "酝酿"):
            if kw in macro_beat:
                return 0.65

        # 过渡章：衔接、过渡、日常
        for kw in ("过渡", "衔接", "日常", "休整", "喘息"):
            if kw in macro_beat:
                return 0.60

        return 0.75

    @staticmethod
    def _resolve_literary_intensity_signal(chapter_mission: Optional[dict]) -> str:
        if not chapter_mission:
            return ""
        chapter_type = str(chapter_mission.get("chapter_type", "")).lower()
        macro_beat = str(chapter_mission.get("macro_beat_description", "")).lower()
        sat_type = str((chapter_mission.get("satisfaction_design") or {}).get("type", "")).lower()
        return f"{chapter_type} {macro_beat} {sat_type}".strip()

    def _resolve_literary_postprocess_profile(
        self,
        *,
        config: PipelineConfig,
        chapter_mission: Optional[dict],
        target_word_count: int,
    ) -> Dict[str, Any]:
        profile = {
            "adaptive_enabled": bool(config.literary_adaptive_postprocess),
            "enable_prose_sculpting": bool(config.enable_prose_sculpting),
            "enable_golden_paragraph": bool(config.enable_golden_paragraph),
            "enable_humanization": bool(config.enable_humanization),
            "reason": "config_static",
        }
        if not config.literary_adaptive_postprocess:
            return profile

        signal = self._resolve_literary_intensity_signal(chapter_mission)
        short_target_threshold = int(getattr(settings, "writer_literary_adaptive_short_target", 2800))
        is_short_target = target_word_count <= short_target_threshold
        is_high_intensity = any(
            kw in signal for kw in ("高潮", "爆发", "决战", "反转", "逆袭", "巅峰", "climax", "boss", "twist")
        )
        is_low_intensity = any(
            kw in signal for kw in ("过渡", "衔接", "铺垫", "日常", "休整", "喘息", "setup", "transition", "slice")
        )

        if is_low_intensity:
            profile["enable_golden_paragraph"] = False
            profile["reason"] = "low_intensity"

        if is_low_intensity and is_short_target:
            profile["enable_prose_sculpting"] = False
            profile["reason"] = "low_intensity_short_target"

        if is_short_target and not is_high_intensity:
            profile["enable_humanization"] = False
            if profile["reason"] == "config_static":
                profile["reason"] = "short_target"

        profile["intensity_signal"] = signal[:120]
        profile["target_word_count"] = target_word_count
        profile["short_target_threshold"] = short_target_threshold
        return profile

    async def _generate_scene_by_scene(
        self,
        *,
        prompt_sections_data: Dict[str, Any],
        writer_prompt: str,
        chapter_mission: Optional[dict],
        forbidden_characters: List[str],
        allowed_new_characters: List[str],
        user_id: int,
        genre_profile: Optional[Dict[str, Any]] = None,
        voice_samples_text: str = "",
    ) -> Dict[str, Any]:
        """场景级分步生成：按 scene_list 逐场景生成，每场景一次 LLM 调用。

        每次调用的 prompt 只包含该场景任务 + 已写内容 + 精简上下文，
        释放 LLM 认知带宽，让它聚焦在"把这 700 字写好"。
        """
        metadata: Dict[str, Any] = {
            "chapter_mission": chapter_mission,
            "pipeline": {"preset": "literary", "mode": "scene_by_scene"},
            "resolved_temperature": self._resolve_temperature(chapter_mission),
        }

        scenes = (chapter_mission or {}).get("scene_list") or []
        if not scenes or len(scenes) < 2:
            scenes = self._build_fallback_scenes(chapter_mission)

        core_context = self._build_slim_context(prompt_sections_data)

        chapter_parts: List[str] = []
        scene_timings: List[int] = []

        for i, scene in enumerate(scenes):
            scene_start = time.perf_counter()
            is_first = i == 0
            is_last = i == len(scenes) - 1

            scene_prompt_parts = []

            if is_first:
                scene_prompt_parts.append(core_context)
            else:
                scene_prompt_parts.append("[精简上下文]\n" + self._compress_context(core_context, max_len=1500))

            if chapter_parts:
                recent_text = "\n\n".join(chapter_parts)
                if len(recent_text) > 2000:
                    recent_text = "（前文省略）\n\n" + recent_text[-2000:]
                scene_prompt_parts.append(f"[已写正文——你要无缝接续]\n{recent_text}")

            scene_goal = scene.get("goal", "推进剧情")
            scene_words = scene.get("target_words", 700)
            scene_location = scene.get("location", "")
            scene_conflict = scene.get("conflict", "")
            human_texture = scene.get("human_texture", [])
            dialogue_noise = scene.get("dialogue_noise", "")

            scene_instruction = f"[本场景任务——场景 {i + 1}/{len(scenes)}]\n"
            scene_instruction += f"- 目标：{scene_goal}\n"
            if scene_location:
                scene_instruction += f"- 地点：{scene_location}\n"
            if scene_conflict:
                scene_instruction += f"- 阻力/冲突：{scene_conflict}\n"
            scene_instruction += f"- 目标字数：约{scene_words}字\n"
            if human_texture:
                scene_instruction += f"- 生活噪音：{'、'.join(human_texture)}\n"
            if dialogue_noise:
                scene_instruction += f"- 对话噪音：{dialogue_noise}\n"

            if is_first:
                scene_instruction += "- 这是开篇，需要吸引读者\n"
            if is_last:
                scene_instruction += "- 这是本章最后一个场景，结尾必须落在具体动作/画面上，戛然而止\n"

            scene_prompt_parts.append(scene_instruction)

            if voice_samples_text and is_first:
                scene_prompt_parts.append(voice_samples_text)

            scene_prompt = "\n\n".join(scene_prompt_parts)

            resolved_temp = self._resolve_temperature(chapter_mission)
            if is_last:
                resolved_temp = min(resolved_temp + 0.05, 0.95)

            response = await self.llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": scene_prompt}],
                temperature=resolved_temp,
                user_id=user_id,
                timeout=60.0,
                response_format=None,
                max_tokens=min(4096, int(max(700, scene_words) * 1.8)),
                disable_thinking=not settings.writer_enable_thinking,
            )
            cleaned = remove_think_tags(response)
            scene_text = sanitize_chapter_plain_text(unwrap_markdown_json(cleaned or response))

            if scene_text:
                chapter_parts.append(scene_text)

            scene_timings.append(int((time.perf_counter() - scene_start) * 1000))

        content = "\n\n".join(chapter_parts)

        omniscient_tolerance = "medium"
        if genre_profile:
            from .genre_profile_service import GenreProfileService
            omniscient_tolerance = GenreProfileService.get_omniscient_tolerance(genre_profile)

        guardrail_result = self.guardrails.check(
            generated_text=content,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            pov=chapter_mission.get("pov") if chapter_mission else None,
            omniscient_tolerance=omniscient_tolerance,
        )
        if not guardrail_result.passed:
            content = self.guardrails.apply_local_patches(content, guardrail_result)

        metadata["scene_timings_ms"] = scene_timings
        metadata["scene_count"] = len(scenes)

        return {"index": 0, "content": content, "metadata": metadata}

    @staticmethod
    def _build_fallback_scenes(chapter_mission: Optional[dict]) -> List[dict]:
        word_budget = (chapter_mission or {}).get("word_budget", {})
        raw_total = word_budget.get("total", 3500) if isinstance(word_budget, dict) else 3500
        total = raw_total if isinstance(raw_total, (int, float)) and raw_total > 0 else 3500
        return [
            {"goal": "开篇：承接上文，建立本章情境", "target_words": int(total * 0.25), "scene": "1"},
            {"goal": "发展：推进核心冲突", "target_words": int(total * 0.45), "scene": "2"},
            {"goal": "高潮+收束：情绪峰值，刀切结尾", "target_words": int(total * 0.30), "scene": "3"},
        ]

    @staticmethod
    def _build_slim_context(prompt_sections_data: Dict[str, Any]) -> str:
        priority_keys = [
            "chapter_goals", "mission_brief", "director_script",
            "story_skeleton", "previous_summary", "previous_tail",
            "writer_blueprint", "forbidden_characters",
            "reference_prose", "fusion_dna",
        ]
        parts = []
        for key in priority_keys:
            val = prompt_sections_data.get(key, "")
            if val:
                parts.append(str(val)[:2000])
        return "\n\n".join(parts)

    @staticmethod
    def _compress_context(context: str, max_len: int = 1500) -> str:
        if len(context) <= max_len:
            return context
        return context[:max_len] + "\n（上下文已压缩）"

    async def _generate_voice_samples(
        self,
        *,
        characters: List[Dict[str, Any]],
        outline_summary: str,
        chapter_mission: Optional[dict],
        user_id: int,
    ) -> str:
        """为出场角色生成对话声纹样本，锁定每个角色的说话方式。"""
        if not characters or len(characters) < 2:
            return ""

        char_list = []
        for ch in characters[:6]:
            name = ch.get("name", "")
            personality = ch.get("personality", "")
            role = ch.get("role", "")
            if name:
                char_list.append(f"- {name}：{role}，{personality}")

        if not char_list:
            return ""

        prompt = (
            f"以下角色将在本章出场。为每个角色写2句对话样本，展示他们的说话方式。\n"
            f"要求：遮住名字能认出是谁。对话要口语化、有性格差异。\n\n"
            f"角色：\n{''.join(char_list)}\n\n"
            f"当前情境：{outline_summary[:200]}\n\n"
            f"格式：每个角色名后跟2句示例台词，简短即可。"
        )

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一个角色对话设计师。为每个角色写出有辨识度的对话样本。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.8,
                user_id=user_id,
                timeout=30.0,
            )
            result = (remove_think_tags(response) or response).strip()
            return f"[角色声纹参考——遮住名字要能认出谁在说话]\n{result}" if result else ""
        except Exception as e:
            logger.warning("声纹样本生成失败（不影响生成）: %s", e)
            return ""

    async def _generate_single_version(
        self,
        *,
        index: int,
        prompt_input: str,
        writer_prompt: str,
        style_hint: Optional[str],
        project_id: str,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        chapter_mission: Optional[dict],
        forbidden_characters: List[str],
        allowed_new_characters: List[str],
        user_id: int,
        writer_blueprint: Dict[str, Any],
        memory_context: Optional[str],
        enhanced_context: Optional[Dict[str, Any]],
        config: PipelineConfig,
        target_word_count: int,
        max_word_count: int = 4000,
        genre_profile: Optional[Dict[str, Any]] = None,
        disable_guardrail_rewrite: bool = False,
        stream_callback: Optional[Callable[[str], Awaitable[None] | None]] = None,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "chapter_mission": chapter_mission,
            "style_hint": style_hint,
            "pipeline": {"preset": config.preset},
            "resolved_temperature": self._resolve_temperature(chapter_mission),
        }

        content = ""
        if config.enable_preview:
            content, preview_meta = await self._generate_with_preview(
                project_id=project_id,
                chapter_number=chapter_number,
                outline_title=outline_title,
                outline_summary=outline_summary,
                writer_blueprint=writer_blueprint,
                memory_context=memory_context,
                style_hint=style_hint,
                enhanced_context=enhanced_context,
                target_word_count=target_word_count,
                user_id=user_id,
            )
            metadata["preview"] = preview_meta

        if not content:
            final_prompt_input = prompt_input
            if style_hint:
                final_prompt_input += f"\n\n[版本风格提示]\n{style_hint}"

            resolved_temp = self._resolve_temperature(chapter_mission)
            # P2: 根据字数上限动态计算 max_tokens，限制物理输出长度
            # 中文约 1.5 tokens/字，取 1.5 作为安全系数
            dynamic_max_tokens = min(
                settings.writer_max_tokens,
                int(max_word_count * 1.5),
            )
            response = await self.llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=resolved_temp,
                user_id=user_id,
                timeout=180.0,
                response_format=None,
                max_tokens=dynamic_max_tokens,
                disable_thinking=not settings.writer_enable_thinking,
                on_chunk=stream_callback,
            )
            cleaned = remove_think_tags(response)
            content = unwrap_markdown_json(cleaned or response)

        omniscient_tolerance = "medium"
        if genre_profile:
            from .genre_profile_service import GenreProfileService
            omniscient_tolerance = GenreProfileService.get_omniscient_tolerance(genre_profile)

        guardrail_result = self.guardrails.check(
            generated_text=content,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            pov=chapter_mission.get("pov") if chapter_mission else None,
            omniscient_tolerance=omniscient_tolerance,
        )
        guardrail_metadata = {"passed": guardrail_result.passed, "violations": []}

        if not guardrail_result.passed:
            guardrail_metadata["violations"] = [
                {"type": v.type, "severity": v.severity, "description": v.description}
                for v in guardrail_result.violations
            ]
            locally_patched = self.guardrails.apply_local_patches(content, guardrail_result)
            guardrail_metadata["local_patch_applied"] = locally_patched != content
            recheck_result = self.guardrails.check(
                generated_text=locally_patched,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                pov=chapter_mission.get("pov") if chapter_mission else None,
                omniscient_tolerance=omniscient_tolerance,
            )
            guardrail_metadata["post_patch_passed"] = recheck_result.passed

            if recheck_result.passed:
                content = locally_patched
            else:
                guardrail_metadata["post_patch_violations"] = [
                    {"type": v.type, "severity": v.severity, "description": v.description}
                    for v in recheck_result.violations
                ]
                # 优化项5: 推迟 LLM 重写到后处理末尾，避免后处理覆盖重写结果
                content = locally_patched
                if not disable_guardrail_rewrite:
                    guardrail_metadata["deferred_llm_rewrite"] = True

        parsed_json = None
        extracted_text = None
        try:
            parsed_json = json.loads(content)
            extracted_text = self._extract_text(parsed_json)
        except Exception:
            parsed_json = None

        final_text = sanitize_chapter_plain_text(extracted_text or content)

        # P3: 超字数后处理压缩——如果生成内容超过上限 102%，使用 LLM 压缩
        overflow_threshold = int(max_word_count * 1.02)
        if len(final_text) > overflow_threshold:
            logger.info(
                "章节字数超限 (%d > %d)，触发压缩 target=%d",
                len(final_text), overflow_threshold, max_word_count,
            )
            compressed = await self._compress_overlength(
                final_text, target_max=max_word_count, user_id=user_id,
            )
            metadata["word_count_compression"] = {
                "original_length": len(final_text),
                "compressed_length": len(compressed),
                "target_max": max_word_count,
            }
            final_text = compressed

        metadata["guardrail"] = guardrail_metadata
        if parsed_json is not None:
            metadata["parsed_json"] = parsed_json

        return {
            "index": index,
            "content": final_text,
            "metadata": metadata,
        }

    @staticmethod
    def _strip_compression_preamble(text: str) -> str:
        """去除 LLM 压缩时可能添加的前言/元注释。

        例如: "可以，下面是精简后的版本（控制在4000字以内）：\n\n正文..."
        或: "### 第49章 全村致富的第一步（精简版）\n\n正文..."
        """
        import re
        lines = text.split("\n")
        skip_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                skip_count += 1
                continue
            # 检测常见 LLM 元注释模式
            if re.match(
                r'^(可以|好的|当然|没问题|下面是|以下是|精简后|精简版|控制在|保留|压缩)',
                stripped,
            ):
                skip_count += 1
                continue
            if re.match(r'^#{1,4}\s+.*(精简版|精简|压缩版|缩写版)', stripped):
                skip_count += 1
                continue
            if re.match(r'^[\(（].*字.*[\)）][：:]?\s*$', stripped):
                skip_count += 1
                continue
            # 第一个看起来像正文的行，停止
            break
        if skip_count > 0:
            text = "\n".join(lines[skip_count:]).lstrip("\n")
        return text

    async def _compress_overlength(
        self,
        chapter_text: str,
        *,
        target_max: int,
        user_id: int,
    ) -> str:
        """使用 LLM 将超字数章节压缩到目标范围内。

        保留核心剧情、对话和关键动作，精简冗余描写和过渡。
        最多重试一次，确保最终结果在目标范围内。
        """
        system_prompt = (
            "你是一个精炼大师。你的任务是将给定的小说章节精简到指定字数以内，"
            "同时保留核心剧情、角色对话、关键动作和情绪转折。\n"
            "精简策略：\n"
            "1. 删除冗余的环境描写和重复的内心戏\n"
            "2. 压缩过渡段落，用更少的笔墨完成场景切换\n"
            "3. 精简对话中的废话，保留有性格的台词\n"
            "4. 不要删除关键剧情节点和伏笔\n"
            "5. 保持开头和结尾的质量\n\n"
            "【绝对禁止】\n"
            "- 禁止输出任何前言、说明、注释、标题或元信息\n"
            "- 禁止写「可以」「下面是」「精简版」等任何非正文内容\n"
            "- 禁止添加章节标题或「精简版」标记\n"
            "- 你的输出第一个字必须是小说正文的第一个字\n"
            "- 你的输出最后一个字必须是小说正文的最后一个字\n"
            "只输出精简后的纯小说正文，没有任何其他内容。"
        )

        current_text = chapter_text
        max_attempts = 2

        for attempt in range(max_attempts):
            user_prompt = (
                f"将以下 {len(current_text)} 字章节正文精简到 {target_max} 字以内。"
                f"直接输出精简后的纯正文，第一个字就是小说内容。\n\n"
                f"{current_text}"
            )
            try:
                response = await self.llm_service.get_llm_response(
                    system_prompt=system_prompt,
                    conversation_history=[{"role": "user", "content": user_prompt}],
                    temperature=0.3,
                    user_id=user_id,
                    timeout=180.0,
                    max_tokens=int(target_max * 1.2),
                )
                cleaned = remove_think_tags(response)
                result = sanitize_chapter_plain_text(unwrap_markdown_json(cleaned or response))

                # 去除 LLM 可能残留的前言/元注释
                if result:
                    result = self._strip_compression_preamble(result)

                if not result or len(result) >= len(current_text):
                    logger.warning("压缩结果无效（更长或为空），保留当前文本 (attempt=%d)", attempt + 1)
                    break

                logger.info(
                    "超字数压缩完成 (attempt=%d): %d -> %d 字 (目标 %d)",
                    attempt + 1, len(current_text), len(result), target_max,
                )
                current_text = result

                # 如果已在目标范围内，停止重试
                if len(current_text) <= target_max:
                    break
            except Exception as e:
                logger.warning("超字数压缩失败 (attempt=%d)，保留当前文本: %s", attempt + 1, e)
                break

        return current_text

    async def _generate_with_preview(
        self,
        *,
        project_id: str,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        writer_blueprint: Dict[str, Any],
        memory_context: Optional[str],
        style_hint: Optional[str],
        enhanced_context: Optional[Dict[str, Any]],
        target_word_count: int,
        user_id: int,
    ) -> Tuple[str, Dict[str, Any]]:
        preview_service = PreviewGenerationService(self.session, self.llm_service, self.prompt_service)
        blueprint_context = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)

        extra_constraints = []
        if enhanced_context:
            if enhanced_context.get("constitution"):
                extra_constraints.append(enhanced_context["constitution"])
            if enhanced_context.get("writer_persona"):
                extra_constraints.append(enhanced_context["writer_persona"])

        if extra_constraints:
            blueprint_context = blueprint_context + "\n\n" + "\n\n".join(extra_constraints)

        preview_result = await preview_service.generate_with_preview(
            project_id=project_id,
            chapter_number=chapter_number,
            outline={"title": outline_title, "summary": outline_summary},
            blueprint_context=blueprint_context,
            emotion_context="（无情绪曲线指导）",
            memory_context=memory_context or "（无记忆层上下文）",
            target_word_count=target_word_count,
            style_hint=style_hint or "",
            user_id=user_id,
        )

        return preview_result.get("full_chapter", ""), preview_result

    @staticmethod
    def _extract_text(value: object) -> Optional[str]:
        return extract_text_from_json(value)

    @staticmethod
    def _build_stage_flags(config: PipelineConfig) -> Dict[str, bool]:
        return {
            "preview": config.enable_preview,
            "optimizer": config.enable_optimizer,
            "polish": config.enable_polish,
            "mission_brief": config.enable_mission_brief,
            "consistency": config.enable_consistency,
            "enrichment": config.enable_enrichment,
            "constitution": config.enable_constitution,
            "persona": config.enable_persona,
            "six_dimension": config.enable_six_dimension,
            "reader_sim": config.enable_reader_sim,
            "self_critique": config.enable_self_critique,
            "memory": config.enable_memory,
            "rag": config.enable_rag,
            "rag_mode": config.rag_mode == "two_stage",
            "scene_by_scene": config.enable_scene_by_scene,
            "prose_sculpting": config.enable_prose_sculpting,
            "golden_paragraph": config.enable_golden_paragraph,
            "reference_prose": config.enable_reference_prose,
            "voice_samples": config.enable_voice_samples,
            "narrative_variety": config.enable_narrative_variety,
            "slim_prompt": config.use_slim_prompt,
            "literary_adaptive_postprocess": config.literary_adaptive_postprocess,
            "fast_path": config.enable_fast_path,
            "disable_guardrail_rewrite": config.disable_guardrail_rewrite,
            "local_anti_hallucination": config.use_local_anti_hallucination,
        }

    @staticmethod
    async def generate_chapter_batch(
        *,
        project_id: str,
        chapter_numbers: List[int],
        user_id: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """流水线批量生成章节。

        采用“前序依赖感知并发”：
        - 若某章节最近可用前章来自本批次，则等待该前章完成（保证上下文连贯）；
        - 若依赖不在本批次内，则可与其他独立章节并发执行。
        每章使用独立 DB session，默认并行度为 1（等价串行，可通过配置提升）。
        """
        sorted_numbers = sorted(set(chapter_numbers))
        if not sorted_numbers:
            return []

        flow_config = flow_config or {}
        max_requested = sorted_numbers[-1]

        try:
            parallel_workers = int(
                flow_config.get(
                    "batch_parallel_workers",
                    getattr(settings, "writer_batch_parallel_workers", 1),
                )
            )
        except (TypeError, ValueError):
            parallel_workers = 1
        parallel_workers = max(1, min(8, parallel_workers))

        existing_generated: set[int] = set()
        try:
            async with AsyncSessionLocal() as dependency_session:
                stmt = (
                    select(Chapter.chapter_number)
                    .where(Chapter.project_id == project_id)
                    .where(Chapter.chapter_number < max_requested)
                    .where(Chapter.selected_version_id.is_not(None))
                )
                rows = await dependency_session.execute(stmt)
                existing_generated = {int(num) for num in rows.scalars().all()}
        except Exception as exc:
            logger.warning("批量依赖预扫描失败，将回退为保守依赖计算: %s", exc)

        dependencies: Dict[int, Optional[int]] = {}
        dependents: Dict[int, List[int]] = {}
        last_requested: Optional[int] = None

        for chapter_number in sorted_numbers:
            dependency: Optional[int] = None
            if last_requested is not None:
                nearest_existing = max((n for n in existing_generated if n < chapter_number), default=None)
                if nearest_existing is None or last_requested > nearest_existing:
                    dependency = last_requested
            dependencies[chapter_number] = dependency
            if dependency is not None:
                dependents.setdefault(dependency, []).append(chapter_number)
            last_requested = chapter_number

        async def _generate_one(chapter_number: int) -> Dict[str, Any]:
            try:
                async with AsyncSessionLocal() as session:
                    orchestrator = PipelineOrchestrator(session)
                    result = await orchestrator.generate_chapter(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        user_id=user_id,
                        writing_notes=writing_notes,
                        flow_config=flow_config,
                    )
                    return {
                        "chapter_number": chapter_number,
                        "status": "success",
                        "result": result,
                    }
            except Exception as e:
                logger.error("批量生成: 章节 %s 失败: %s", chapter_number, e)
                return {
                    "chapter_number": chapter_number,
                    "status": "failed",
                    "error": str(e)[:500],
                }

        ready = [num for num in sorted_numbers if dependencies.get(num) is None]
        ready.sort()
        running: Dict[asyncio.Task, int] = {}
        results_by_chapter: Dict[int, Dict[str, Any]] = {}
        remaining = set(sorted_numbers)

        while remaining:
            while ready and len(running) < parallel_workers:
                chapter_number = ready.pop(0)
                if chapter_number not in remaining:
                    continue
                task = asyncio.create_task(_generate_one(chapter_number))
                running[task] = chapter_number

            if not running:
                fallback = min(remaining)
                logger.warning("批量调度出现空转，回退执行章节 %s", fallback)
                ready.append(fallback)
                continue

            done, _ = await asyncio.wait(set(running.keys()), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                chapter_number = running.pop(task)
                remaining.discard(chapter_number)
                task_result = task.result()
                results_by_chapter[chapter_number] = task_result

                logger.info(
                    "批量生成: 章节 %s 完成 (%d/%d)",
                    chapter_number,
                    len(results_by_chapter),
                    len(sorted_numbers),
                )

                for dependent in dependents.get(chapter_number, []):
                    if dependent in remaining:
                        ready.append(dependent)
                ready.sort()

        return [results_by_chapter[num] for num in sorted_numbers]

    async def _load_project_reference_novels(
        self,
        project: NovelProject,
        reference_service: ReferenceNovelLibraryService,
    ) -> List[ReferenceNovel]:
        ids = project.reference_novel_ids or []
        if not ids:
            return []
        novels = await reference_service.get_by_ids(ids)
        return [n for n in novels if n.status == "ready"]


__all__ = ["PipelineOrchestrator", "PipelineConfig"]
