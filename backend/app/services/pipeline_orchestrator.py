# AIMETA P=写作流水线编排_统一生成入口|R=上下文汇聚_生成_审查_优化|NR=不含API路由|E=PipelineOrchestrator|X=internal|A=编排器|D=fastapi,sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.novel import Chapter
from ..models.project_memory import ProjectMemory
from ..repositories.system_config_repository import SystemConfigRepository
from ..services.ai_review_service import AIReviewService
from ..services.chapter_context_service import ChapterContextService
from ..services.chapter_guardrails import ChapterGuardrails
from ..services.consistency_service import ConsistencyService, ViolationSeverity
from ..services.enhanced_writing_flow import EnhancedWritingFlow
from ..services.enrichment_service import EnrichmentService
from ..services.llm_service import LLMService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService, FilteredContext
from ..services.memory_layer_service import MemoryLayerService
from ..services.novel_service import NovelService
from ..services.preview_generation_service import PreviewGenerationService
from ..services.prompt_service import PromptService
from ..services.reader_simulator_service import ReaderSimulatorService, ReaderType
from ..services.self_critique_service import CritiqueDimension, SelfCritiqueService
from ..services.vector_store_service import VectorStoreService
from ..services.writer_context_builder import WriterContextBuilder
from ..services.platinum_writing_context import (
    PLATINUM_WRITING_BRIEF_FALLBACK,
    build_foreshadowing_urgency_brief,
    build_hook_continuity_brief,
    build_platinum_rhythm_brief,
)
from ..utils.json_utils import remove_think_tags, repair_json, sanitize_chapter_plain_text, unwrap_markdown_json

logger = logging.getLogger(__name__)

CHAPTER_MIN_WORDS = 2000
CHAPTER_MAX_WORDS = 5000
CHAPTER_RECOMMENDED_WORDS = 3000
CHAPTER_WORD_COUNT_RULE = (
    f"本章正文必须在 {CHAPTER_MIN_WORDS} 到 {CHAPTER_MAX_WORDS} 字之间（含边界）。"
    f"推荐目标约 {CHAPTER_RECOMMENDED_WORDS} 字，建议按开头钩子 10%、剧情发展 50%、"
    "高潮爆点 33%、结尾钩子 7% 分配。"
)


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
    enable_fingerprint: bool = False


class PipelineOrchestrator:
    """统一写作流水线编排器。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.novel_service = NovelService(session)
        self.context_builder = WriterContextBuilder()
        self.guardrails = ChapterGuardrails()

    async def generate_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        config = await self._resolve_config(flow_config)
        project = await self.novel_service.ensure_project_owner(project_id, user_id)

        outline = await self.novel_service.get_outline(project_id, chapter_number)
        if not outline:
            raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

        chapter = await self.novel_service.get_or_create_chapter(project_id, chapter_number)
        chapter.real_summary = None
        chapter.selected_version_id = None
        chapter.status = "generating"
        await self.session.commit()

        outlines_map = {item.chapter_number: item for item in project.outlines}
        history_context = await self._collect_history_context(
            project_id=project_id,
            chapter_number=chapter_number,
            outlines_map=outlines_map,
            chapters=project.chapters,
            user_id=user_id,
        )

        project_schema = await self.novel_service._serialize_project(project)
        blueprint_dict = self._normalize_blueprint(project_schema.blueprint.model_dump())

        outline_title = outline.title or f"第{outline.chapter_number}章"
        outline_summary = outline.summary or "暂无摘要"
        writing_notes = writing_notes or "无额外写作指令"

        all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

        pattern_constraint = self._build_pattern_differentiation(
            history_context.get("completed_chapters", [])
        )

        chapter_mission = await self._generate_chapter_mission(
            blueprint_dict=blueprint_dict,
            previous_summary=history_context["previous_summary"],
            previous_tail=history_context["previous_tail"],
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            introduced_characters=[],
            all_characters=all_characters,
            user_id=user_id,
            pattern_constraint=pattern_constraint,
        )

        allowed_new_characters = chapter_mission.get("allowed_new_characters", []) if chapter_mission else []

        visibility_context = self.context_builder.build_visibility_context(
            blueprint=blueprint_dict,
            completed_summaries=history_context["completed_summaries"],
            previous_tail=history_context["previous_tail"],
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            allowed_new_characters=allowed_new_characters,
        )

        writer_blueprint = visibility_context["writer_blueprint"]
        forbidden_characters = visibility_context["forbidden_characters"]
        introduced_characters = visibility_context["introduced_characters"]

        logger.info(
            "Pipeline context: project=%s chapter=%s introduced=%d allowed_new=%d forbidden=%d",
            project_id,
            chapter_number,
            len(introduced_characters),
            len(allowed_new_characters),
            len(forbidden_characters),
        )

        mission_brief_text = None
        if chapter_mission:
            mission_brief_text = await self._generate_mission_brief(
                chapter_mission=chapter_mission,
                previous_summary=history_context["previous_summary"],
                previous_tail=history_context["previous_tail"],
                outline_title=outline_title,
                outline_summary=outline_summary,
                writing_notes=writing_notes,
                introduced_characters=introduced_characters,
                forbidden_characters=forbidden_characters,
                user_id=user_id,
            )

        enhanced_flow = None
        enhanced_context = None
        if config.enable_constitution or config.enable_persona or config.enable_foreshadowing or config.enable_faction:
            enhanced_flow = EnhancedWritingFlow(self.session, self.llm_service, self.prompt_service)
            enhanced_context = await enhanced_flow.prepare_writing_context(
                project_id=project_id,
                chapter_number=chapter_number,
                chapter_outline=outline_summary,
            )

        memory_context = None
        if config.enable_memory:
            memory_context = await self._get_memory_context(
                project_id=project_id,
                chapter_number=chapter_number,
                involved_characters=introduced_characters,
            )

        project_memory_text = await self._get_project_memory_text(project_id)

        rag_context = None
        knowledge_context = None
        rag_stats = None
        if config.enable_rag:
            if config.rag_mode == "two_stage":
                knowledge_context, rag_stats = await self._get_two_stage_rag_context(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    writing_notes=writing_notes,
                    pov_character=self._resolve_pov_character(chapter_mission),
                    user_id=user_id,
                    retrieval_mode=config.rag_retrieval_mode,
                )
            else:
                rag_context = await self._get_rag_context(
                    project_id=project_id,
                    outline_title=outline_title,
                    outline_summary=outline_summary,
                    writing_notes=writing_notes,
                    user_id=user_id,
                    retrieval_mode=config.rag_retrieval_mode,
                )
                rag_stats = {
                    "mode": "simple",
                    "chunks": len(rag_context.get("chunks", [])) if rag_context else 0,
                    "summaries": len(rag_context.get("summaries", [])) if rag_context else 0,
                }

        writer_prompt = await self.prompt_service.get_prompt("writing_v2")
        if not writer_prompt:
            writer_prompt = await self.prompt_service.get_prompt("writing")
        if not writer_prompt:
            raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置")

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
        foreshadowing_urgency_brief = await build_foreshadowing_urgency_brief(
            session=self.session,
            project_id=project_id,
            chapter_number=chapter_number,
        )
        hook_continuity_brief = build_hook_continuity_brief(
            previous_summary=history_context["previous_summary"],
            previous_tail=history_context["previous_tail"],
            chapter_mission=chapter_mission,
        )

        # ---- 作者风格指纹 ----
        fingerprint_context: Optional[str] = None
        if config.enable_fingerprint:
            try:
                from .author_fingerprint_service import AuthorFingerprintService
                fp_service = AuthorFingerprintService()
                # 从已完成章节的选中版本提取全文
                chapter_texts = [
                    ch.selected_version.content
                    for ch in project.chapters
                    if ch.chapter_number < chapter_number
                    and ch.selected_version
                    and ch.selected_version.content
                ]
                fingerprint_context = fp_service.get_or_extract(project_id, chapter_texts)
            except Exception as e:
                logger.warning("风格指纹提取失败（不影响生成）: %s", e)

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
            story_skeleton=history_context.get("story_skeleton"),
            genre_prompt_injection=genre_prompt_injection,
            fingerprint_context=fingerprint_context,
        )

        if enhanced_flow and enhanced_context:
            prompt_sections = enhanced_flow.build_enhanced_prompt_sections(prompt_sections, enhanced_context)

        prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
        logger.debug("Pipeline prompt length: %s chars", len(prompt_input))

        version_count = config.version_count
        version_style_hints = self._resolve_style_hints(enhanced_context, version_count)

        versions: List[Dict[str, Any]] = []
        for idx in range(version_count):
            style_hint = version_style_hints[idx] if idx < len(version_style_hints) else None
            versions.append(
                await self._generate_single_version(
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
                    genre_profile=genre_profile,
                )
            )

        best_version_index, ai_review_result = await self._run_ai_review(
            versions=versions,
            chapter_mission=chapter_mission,
            user_id=user_id,
        )

        review_summaries: Dict[str, Any] = {}
        if ai_review_result:
            review_summaries["ai_review"] = ai_review_result

        if versions:
            best_version_index = max(0, min(best_version_index, len(versions) - 1))
        else:
            best_version_index = 0

        if versions:
            best_version = versions[best_version_index]
            best_content = best_version["content"]

            if ai_review_result and (ai_review_result.get("flaws") or ai_review_result.get("suggestions")):
                best_content, revision_report = await self._revise_with_review_feedback(
                    best_content,
                    critical_flaws=ai_review_result.get("flaws") or [],
                    refinement_suggestions=ai_review_result.get("suggestions") or "",
                    chapter_mission=chapter_mission,
                    user_id=user_id,
                )
                review_summaries["review_driven_revision"] = revision_report

            if enhanced_flow and config.enable_six_dimension:
                review_result = await enhanced_flow.post_generation_review(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_title=outline_title,
                    chapter_content=best_content,
                    chapter_plan=json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                    previous_summary=history_context["previous_summary"],
                )
                review_summaries["enhanced_review"] = review_result

            if config.enable_self_critique:
                best_content, critique_summary = await self._run_self_critique(
                    best_content,
                    user_id=user_id,
                    context={
                        "character_profiles": json.dumps(writer_blueprint.get("characters", []), ensure_ascii=False),
                        "previous_summary": history_context["previous_summary"],
                    },
                )
                review_summaries["self_critique"] = critique_summary

            if config.enable_reader_sim:
                reader_feedback = await self._run_reader_simulation(
                    best_content,
                    chapter_number=chapter_number,
                    previous_summary=history_context["previous_summary"],
                    user_id=user_id,
                )
                review_summaries["reader_simulator"] = reader_feedback

            if config.enable_consistency:
                best_content, consistency_report = await self._run_consistency_check(
                    project_id=project_id,
                    chapter_text=best_content,
                    user_id=user_id,
                )
                review_summaries["consistency"] = consistency_report

            if config.enable_anti_hallucination:
                try:
                    from .anti_hallucination_service import AntiHallucinationService
                    ah_service = AntiHallucinationService(self.session, self.llm_service)
                    ah_report = await ah_service.check_chapter(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_text=best_content,
                        user_id=user_id,
                    )
                    review_summaries["anti_hallucination"] = {
                        "passed": ah_report.passed,
                        "registered_count": ah_report.registered_count,
                        "warning_count": ah_report.warning_count,
                        "critical_count": ah_report.critical_count,
                        "report": AntiHallucinationService.format_report_for_review(ah_report),
                    }
                except Exception as e:
                    logger.warning("反幻觉检查失败（不影响生成）: %s", e)
                    review_summaries["anti_hallucination"] = {"error": str(e)}

            # ---- 人味化扫描与修复 ----
            if config.enable_humanization:
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

            if config.enable_optimizer:
                best_content, optimizer_report = await self._run_optimizer(best_content, user_id=user_id)
                review_summaries["optimizer"] = optimizer_report

            if config.enable_enrichment:
                best_content, enrichment_report = await self._run_enrichment(
                    best_content,
                    user_id=user_id,
                )
                if enrichment_report:
                    review_summaries["enrichment"] = enrichment_report

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

            best_version["content"] = best_content
            best_version.setdefault("metadata", {})["review_summaries"] = review_summaries

        contents = [v.get("content", "") for v in versions]
        metadata = [v.get("metadata") for v in versions]
        versions_models = await self.novel_service.replace_chapter_versions(chapter, contents, metadata)

        variants = []
        for idx, version_model in enumerate(versions_models):
            variant = {
                "index": idx,
                "version_id": version_model.id,
                "content": versions[idx].get("content", ""),
                "metadata": versions[idx].get("metadata"),
            }
            variants.append(variant)

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
            },
        }

    async def _resolve_config(self, flow_config: Optional[Dict[str, Any]]) -> PipelineConfig:
        flow_config = flow_config or {}
        preset = flow_config.get("preset", "basic")

        config = PipelineConfig(preset=preset)
        config.version_count = await self._resolve_version_count(flow_config.get("versions"))

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
            config.rag_mode = "two_stage"
            # enhanced+ 预设启用反幻觉
            if getattr(settings, "enable_entity_registry", True):
                config.enable_anti_hallucination = True

        if preset == "enhanced":
            config.enable_six_dimension = True

        if preset == "ultimate":
            config.enable_memory = True

        if preset == "platinum":
            config.enable_memory = True
            config.enable_six_dimension = True
            config.enable_self_critique = True
            config.enable_reader_sim = True
            config.enable_consistency = True

        if preset == "basic":
            config.enable_rag = True

        for key in (
            "enable_preview",
            "enable_optimizer",
            "enable_consistency",
            "enable_enrichment",
            "async_finalize",
            "enable_rag",
        ):
            if key in flow_config and flow_config[key] is not None:
                setattr(config, key, bool(flow_config[key]))

        if flow_config.get("rag_mode"):
            config.rag_mode = str(flow_config["rag_mode"])

        if flow_config.get("rag_retrieval_mode"):
            config.rag_retrieval_mode = str(flow_config["rag_retrieval_mode"])

        if flow_config.get("pacing_model"):
            config.pacing_model = str(flow_config["pacing_model"])

        if preset == "ultimate":
            config.enable_preview = False
            config.enable_optimizer = False
            config.enable_consistency = False
            config.enable_enrichment = False
            config.enable_six_dimension = False
            config.enable_reader_sim = False
            config.enable_self_critique = False

        return config

    async def _resolve_version_count(self, requested_count: Optional[int]) -> int:
        if requested_count:
            try:
                count = int(requested_count)
                return max(1, count)
            except (TypeError, ValueError):
                pass

        repo = SystemConfigRepository(self.session)
        for key in ("writer.chapter_versions", "writer.version_count"):
            record = await repo.get_by_key(key)
            if record and record.value:
                try:
                    val = int(record.value)
                    if val >= 1:
                        return val
                except ValueError:
                    pass

        for env in ("WRITER_CHAPTER_VERSION_COUNT", "WRITER_CHAPTER_VERSIONS", "WRITER_VERSION_COUNT"):
            v = os.getenv(env)
            if v:
                try:
                    val = int(v)
                    if val >= 1:
                        return val
                except ValueError:
                    pass

        return int(settings.writer_chapter_versions)

    async def _collect_history_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        outlines_map: Dict[int, Any],
        chapters: List[Chapter],
        user_id: int,
    ) -> Dict[str, Any]:
        completed_summaries = []
        completed_chapters = []
        latest_prev_number = -1
        previous_summary_text = ""
        previous_tail_excerpt = ""

        for existing in chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                summary = await self.llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=user_id,
                    timeout=180.0,
                )
                existing.real_summary = remove_think_tags(summary)
                await self.session.commit()

            completed_chapters.append(
                {
                    "chapter_number": existing.chapter_number,
                    "title": outlines_map.get(existing.chapter_number).title
                    if outlines_map.get(existing.chapter_number)
                    else f"第{existing.chapter_number}章",
                    "summary": existing.real_summary,
                    "opening_excerpt": existing.selected_version.content[:150] if existing.selected_version.content else "",
                    "ending_excerpt": existing.selected_version.content[-150:] if existing.selected_version.content and len(existing.selected_version.content) > 150 else (existing.selected_version.content or ""),
                    "chapter_mission_patterns": self._extract_mission_patterns(existing.selected_version),
                }
            )
            completed_summaries.append(existing.real_summary or "")

            if existing.chapter_number > latest_prev_number:
                latest_prev_number = existing.chapter_number
                previous_summary_text = existing.real_summary or ""
                previous_tail_excerpt = self._extract_tail_excerpt(existing.selected_version.content)

        story_skeleton = self._build_story_skeleton(completed_chapters, chapter_number)

        return {
            "completed_chapters": completed_chapters,
            "completed_summaries": completed_summaries,
            "previous_summary": previous_summary_text or "暂无（这是第一章）",
            "previous_tail": previous_tail_excerpt or "暂无（这是第一章）",
            "story_skeleton": story_skeleton,
        }

    @staticmethod
    def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
        if not text:
            return ""
        stripped = text.strip()
        if len(stripped) <= limit:
            return stripped
        return stripped[-limit:]

    @staticmethod
    def _build_story_skeleton(
        completed_chapters: List[Dict[str, Any]],
        current_chapter: int,
    ) -> Optional[str]:
        """从历史章节中采样构建故事骨架，为 Writer 提供长程上下文。

        采样策略：
        - ≤5章：全部包含
        - >5章：第1章 + 每隔N章采样 + 最近2章（最近2章已有专门的 previous_summary，此处不重复）
        """
        if not completed_chapters or len(completed_chapters) <= 1:
            return None

        sorted_chapters = sorted(completed_chapters, key=lambda c: c["chapter_number"])

        # 排除最近一章（已有 [上一章摘要] 覆盖）
        candidates = [c for c in sorted_chapters if c["chapter_number"] < current_chapter - 1]
        if not candidates:
            return None

        if len(candidates) <= 5:
            sampled = candidates
        else:
            # 第1章必选 + 均匀采样中间 + 倒数第2章
            sampled = [candidates[0]]
            step = max(2, len(candidates) // 4)
            for i in range(step, len(candidates) - 1, step):
                sampled.append(candidates[i])
            if candidates[-1] not in sampled:
                sampled.append(candidates[-1])

        lines = []
        for ch in sampled:
            num = ch["chapter_number"]
            title = ch.get("title", f"第{num}章")
            summary = ch.get("summary", "")
            if summary and len(summary) > 150:
                summary = summary[:150] + "…"
            lines.append(f"第{num}章 {title}：{summary}")

        return "\n".join(lines)

    @staticmethod
    def _normalize_blueprint(blueprint_dict: Dict[str, Any]) -> Dict[str, Any]:
        if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
            for relation in blueprint_dict["relationships"]:
                if "character_from" in relation:
                    relation["from"] = relation.pop("character_from")
                if "character_to" in relation:
                    relation["to"] = relation.pop("character_to")
        return blueprint_dict

    @staticmethod
    def _extract_mission_patterns(selected_version) -> Dict[str, str]:
        """从 version metadata 中提取 opening_hook_type、chapter_end_style、satisfaction_design.type。"""
        if not selected_version:
            return {}
        metadata = getattr(selected_version, "metadata_", None) or {}
        mission = metadata.get("chapter_mission") or {}
        if not mission:
            return {}
        result: Dict[str, str] = {}
        if mission.get("opening_hook_type"):
            result["opening_hook_type"] = mission["opening_hook_type"]
        if mission.get("chapter_end_style"):
            result["chapter_end_style"] = mission["chapter_end_style"]
        sat = mission.get("satisfaction_design")
        if isinstance(sat, dict) and sat.get("type"):
            result["satisfaction_type"] = sat["type"]
        return result

    @staticmethod
    def _build_pattern_differentiation(completed_chapters: List[Dict[str, Any]]) -> str:
        """分析最近章节的开头/结尾/爽感模式，生成差异化约束文本。"""
        if not completed_chapters:
            return ""

        sorted_chapters = sorted(completed_chapters, key=lambda c: c["chapter_number"])
        constraints: List[str] = []

        # 分析最近3章的开头类型和结尾类型
        recent_3 = sorted_chapters[-3:]
        opening_types = [
            c["chapter_mission_patterns"].get("opening_hook_type", "")
            for c in recent_3
            if c.get("chapter_mission_patterns")
        ]
        opening_types = [t for t in opening_types if t]
        if len(opening_types) >= 2 and len(set(opening_types)) == 1:
            constraints.append(f"最近{len(opening_types)}章开头均为「{opening_types[0]}」类型，本章必须使用不同的开头类型。")

        ending_types = [
            c["chapter_mission_patterns"].get("chapter_end_style", "")
            for c in recent_3
            if c.get("chapter_mission_patterns")
        ]
        ending_types = [t for t in ending_types if t]
        if len(ending_types) >= 2 and len(set(ending_types)) == 1:
            constraints.append(f"最近{len(ending_types)}章结尾均为「{ending_types[0]}」风格，本章必须使用不同的结尾风格。")

        # 分析最近5章的爽感模式
        recent_5 = sorted_chapters[-5:]
        sat_types = [
            c["chapter_mission_patterns"].get("satisfaction_type", "")
            for c in recent_5
            if c.get("chapter_mission_patterns")
        ]
        sat_types = [t for t in sat_types if t and t != "无（蓄力中）"]
        if len(sat_types) >= 3:
            from collections import Counter
            counter = Counter(sat_types)
            most_common_type, most_common_count = counter.most_common(1)[0]
            if most_common_count >= 3:
                constraints.append(f"最近5章中「{most_common_type}」爽感出现{most_common_count}次，本章应尝试不同类型的爽感设计。")

        # 对比最近3章开头摘录，检测开头模式雷同
        opening_excerpts = [
            c.get("opening_excerpt", "")[:80]
            for c in recent_3
            if c.get("opening_excerpt")
        ]
        if opening_excerpts:
            constraints.append(
                "近期章节开头摘录供参考（避免相似开头）：\n"
                + "\n".join(f"- 第{c['chapter_number']}章：「{c.get('opening_excerpt', '')[:80]}…」" for c in recent_3 if c.get("opening_excerpt"))
            )

        if not constraints:
            return ""

        return "[模式差异化约束]\n" + "\n".join(constraints)

    async def _generate_chapter_mission(
        self,
        *,
        blueprint_dict: Dict[str, Any],
        previous_summary: str,
        previous_tail: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        introduced_characters: List[str],
        all_characters: List[str],
        user_id: int,
        pattern_constraint: str = "",
    ) -> Optional[dict]:
        plan_prompt = await self.prompt_service.get_prompt("chapter_plan")
        if not plan_prompt:
            logger.warning("未配置 chapter_plan 提示词，跳过导演脚本生成")
            return None

        plan_input = f"""
[上一章摘要]
{previous_summary}

[上一章结尾]
{previous_tail}

[当前章节大纲]
标题：{outline_title}
摘要：{outline_summary}

[已登场角色]
{json.dumps(introduced_characters, ensure_ascii=False) if introduced_characters else "暂无"}

[全部角色]
{json.dumps(all_characters, ensure_ascii=False)}

[写作指令]
{writing_notes}
"""
        if pattern_constraint:
            plan_input += f"\n{pattern_constraint}\n"

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=plan_prompt,
                conversation_history=[{"role": "user", "content": plan_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=120.0,
            )
            cleaned = remove_think_tags(response)
            if not cleaned:
                logger.info("导演脚本: remove_think_tags 后为空，回退原始响应 (len=%d)", len(response))
                cleaned = response
            normalized = unwrap_markdown_json(cleaned)
            if not normalized:
                logger.warning("导演脚本: unwrap_markdown_json 结果为空")
                return None
            try:
                mission = json.loads(normalized)
            except json.JSONDecodeError:
                mission = json.loads(repair_json(normalized))
            logger.info("章节导演脚本生成完成: macro_beat=%s", mission.get("macro_beat"))
            return mission
        except Exception as exc:
            logger.warning("生成章节导演脚本失败，将使用默认模式: %s", exc)
            return None

    async def _generate_mission_brief(
        self,
        *,
        chapter_mission: dict,
        previous_summary: str,
        previous_tail: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        introduced_characters: List[str],
        forbidden_characters: List[str],
        user_id: int,
    ) -> Optional[str]:
        """将 ChapterMission JSON 转换为人类可读的创作任务书。"""
        brief_prompt = await self.prompt_service.get_prompt("mission_brief")
        if not brief_prompt:
            logger.info("未配置 mission_brief 提示词，将使用原始 JSON")
            return None

        brief_input = f"""[章节导演脚本]
{json.dumps(chapter_mission, ensure_ascii=False, indent=2)}

[上一章摘要]
{previous_summary}

[上一章结尾]
{previous_tail}

[当前章节目标]
标题：{outline_title}
摘要：{outline_summary}
写作要求：{writing_notes}

[已登场角色]
{", ".join(introduced_characters) if introduced_characters else "暂无"}

[禁止角色]
{", ".join(forbidden_characters) if forbidden_characters else "无"}"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=brief_prompt,
                conversation_history=[{"role": "user", "content": brief_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=120.0,
            )
            cleaned = remove_think_tags(response)
            if not cleaned or not cleaned.strip():
                logger.warning("创作任务书生成结果为空，回退原始 JSON")
                return None
            logger.info("创作任务书生成完成 (len=%d)", len(cleaned))
            return cleaned.strip()
        except Exception as exc:
            logger.warning("生成创作任务书失败，将回退原始 JSON: %s", exc)
            return None

    async def _get_rag_context(
        self,
        *,
        project_id: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        user_id: int,
        retrieval_mode: str = "vector",
    ) -> Dict[str, Any]:
        if not settings.vector_store_enabled:
            return {"chunks": [], "summaries": []}

        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过 RAG: %s", exc)
            return {"chunks": [], "summaries": []}

        query_parts = [outline_title, outline_summary]
        if writing_notes:
            query_parts.append(writing_notes)
        rag_query = "\n".join(part for part in query_parts if part)

        context_service = ChapterContextService(llm_service=self.llm_service, vector_store=vector_store)
        rag_context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=rag_query or outline_title or outline_summary,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
        )
        return {
            "chunks": rag_context.chunk_texts() if rag_context.chunks else [],
            "summaries": rag_context.summary_lines() if rag_context.summaries else [],
        }

    async def _get_two_stage_rag_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        writing_notes: str,
        pov_character: Optional[str],
        user_id: int,
        retrieval_mode: str = "vector",
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        if not settings.vector_store_enabled:
            return None, {"mode": "two_stage", "enabled": False}

        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过两层 RAG: %s", exc)
            return None, {"mode": "two_stage", "enabled": False, "error": str(exc)}

        sync_session = getattr(self.session, "sync_session", self.session)
        retrieval_service = KnowledgeRetrievalService(sync_session, self.llm_service, vector_store)
        filtered = await retrieval_service.retrieve_and_filter(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            pov_character=pov_character,
            user_guidance=writing_notes,
            top_k=settings.vector_top_k_chunks,
            retrieval_mode=retrieval_mode,
        )
        context_text = self._format_filtered_context(filtered)
        stats = filtered.stats or {}
        stats["mode"] = "two_stage"
        return context_text, stats

    async def _get_project_memory_text(self, project_id: str) -> Optional[str]:
        result = await self.session.execute(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        memory = result.scalars().first()
        if not memory:
            return None

        parts = []
        if memory.global_summary:
            parts.append(f"### 全局摘要\n{memory.global_summary}")
        if memory.plot_arcs:
            parts.append("### 剧情线追踪\n" + json.dumps(memory.plot_arcs, ensure_ascii=False, indent=2))
        if not parts:
            return None
        return "\n\n".join(parts)

    async def _get_memory_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        involved_characters: List[str],
    ) -> str:
        memory_layer = MemoryLayerService(self.session, self.llm_service, self.prompt_service)
        return await memory_layer.get_memory_context(project_id, chapter_number, involved_characters)

    @staticmethod
    def _build_prompt_sections(
        *,
        writer_blueprint: Dict[str, Any],
        previous_summary: str,
        previous_tail: str,
        chapter_mission: Optional[dict],
        mission_brief_text: Optional[str],
        rag_context: Optional[Dict[str, Any]],
        knowledge_context: Optional[str],
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        forbidden_characters: List[str],
        project_memory_text: Optional[str],
        memory_context: Optional[str],
        platinum_writing_brief: Optional[str],
        platinum_rhythm_brief: Optional[str],
        foreshadowing_urgency_brief: Optional[str],
        hook_continuity_brief: Optional[str],
        story_skeleton: Optional[str] = None,
        genre_prompt_injection: Optional[str] = None,
        fingerprint_context: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        blueprint_text = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)
        forbidden_text = json.dumps(forbidden_characters, ensure_ascii=False) if forbidden_characters else "无"

        # --- TIER 1: 核心指令（利用首因效应，放在最前面）---
        sections: List[Tuple[str, str]] = [
            ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}"),
        ]

        if mission_brief_text:
            sections.append(("[创作任务书](本章写作的核心执行指南，必须严格遵循)", mission_brief_text))
        elif chapter_mission:
            mission_text = json.dumps(chapter_mission, ensure_ascii=False, indent=2)
            sections.append(("[章节导演脚本](JSON)", mission_text))

        sections.append(("[章节字数要求]", CHAPTER_WORD_COUNT_RULE))

        # --- TIER 2: 上下文参考（中间位置）---
        if story_skeleton:
            sections.append(("[故事骨架](前情关键节点采样，帮助你把握全局走向)", story_skeleton))

        sections.extend(
            [
                ("[上一章摘要]", previous_summary or "暂无（这是第一章）"),
                ("[上一章结尾]", previous_tail or "暂无（这是第一章）"),
                ("[世界蓝图](JSON，已裁剪)", blueprint_text),
            ]
        )

        if project_memory_text:
            sections.append(("[项目长期记忆](摘要/剧情线)", project_memory_text))
        if memory_context:
            sections.append(("[记忆层上下文]", memory_context))

        if knowledge_context:
            sections.append(("[RAG精筛上下文](含POV裁剪)", knowledge_context))

        if rag_context:
            rag_chunks_text = "\n\n".join(rag_context.get("chunks", [])) or "未检索到章节片段"
            rag_summaries_text = "\n".join(rag_context.get("summaries", [])) or "未检索到章节摘要"
            sections.append(("[检索到的剧情上下文](Markdown)", rag_chunks_text))
            sections.append(("[检索到的章节摘要](Markdown)", rag_summaries_text))

        # --- TIER 3: 补充约束（利用近因效应，放在最后面）---
        if genre_prompt_injection:
            sections.append(("[题材写作约束]", genre_prompt_injection))
        if fingerprint_context:
            sections.append(("[作者风格指纹]", fingerprint_context))
        if platinum_rhythm_brief:
            sections.append(("[白金节奏控制](Quest/Fire/Constellation)", platinum_rhythm_brief))
        if foreshadowing_urgency_brief:
            sections.append(("[高优先级伏笔提醒]", foreshadowing_urgency_brief))
        if hook_continuity_brief:
            sections.append(("[追更钩子连续性]", hook_continuity_brief))
        if platinum_writing_brief:
            sections.append(("[白金写作准则](硬约束)", platinum_writing_brief))
        sections.append(("[禁止角色](本章不允许提及)", forbidden_text))

        return sections

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
        genre_profile: Optional[Dict[str, Any]] = None,
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
                user_id=user_id,
            )
            metadata["preview"] = preview_meta

        if not content:
            final_prompt_input = prompt_input
            if style_hint:
                final_prompt_input += f"\n\n[版本风格提示]\n{style_hint}"

            resolved_temp = self._resolve_temperature(chapter_mission)
            response = await self.llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=resolved_temp,
                user_id=user_id,
                timeout=600.0,
                response_format=None,
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
            violations_text = self.guardrails.format_violations_for_rewrite(guardrail_result)
            content = await self._rewrite_with_guardrails(
                original_text=content,
                chapter_mission=chapter_mission,
                violations_text=violations_text,
                user_id=user_id,
            )

        parsed_json = None
        extracted_text = None
        try:
            parsed_json = json.loads(content)
            extracted_text = self._extract_text(parsed_json)
        except Exception:
            parsed_json = None

        final_text = sanitize_chapter_plain_text(extracted_text or content)

        metadata["guardrail"] = guardrail_metadata
        if parsed_json is not None:
            metadata["parsed_json"] = parsed_json

        return {
            "index": index,
            "content": final_text,
            "metadata": metadata,
        }

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
            style_hint=style_hint or "",
            user_id=user_id,
        )

        return preview_result.get("full_chapter", ""), preview_result

    async def _rewrite_with_guardrails(
        self,
        *,
        original_text: str,
        chapter_mission: Optional[dict],
        violations_text: str,
        user_id: int,
    ) -> str:
        rewrite_prompt = await self.prompt_service.get_prompt("rewrite_guardrails")
        if not rewrite_prompt:
            logger.warning("未配置 rewrite_guardrails 提示词，跳过自动修复")
            return original_text

        rewrite_input = f"""
[原文]
{original_text}

[章节导演脚本]
{json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无"}

[违规列表]
{violations_text}
"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=rewrite_prompt,
                conversation_history=[{"role": "user", "content": rewrite_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=300.0,
                response_format=None,
            )
            cleaned = remove_think_tags(response)
            if not cleaned.strip():
                logger.warning("护栏重写结果去除 think 标签后为空，回退到原文")
                return original_text
            return cleaned
        except Exception as exc:
            logger.warning("自动修复失败，返回原文: %s", exc)
            return original_text

    @staticmethod
    def _extract_text(value: object) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("content", "chapter_content", "chapter_text", "text", "body", "story"):
                if value.get(key):
                    nested = PipelineOrchestrator._extract_text(value.get(key))
                    if nested:
                        return nested
            return None
        if isinstance(value, list):
            for item in value:
                nested = PipelineOrchestrator._extract_text(item)
                if nested:
                    return nested
        return None

    async def _run_ai_review(
        self,
        *,
        versions: List[Dict[str, Any]],
        chapter_mission: Optional[dict],
        user_id: int,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        if len(versions) <= 1:
            return 0, None

        contents = [v.get("content", "") for v in versions]
        try:
            ai_review_service = AIReviewService(self.llm_service, self.prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning("AI 评审失败，跳过: %s", exc)
            return 0, None

        if not ai_review_result:
            return 0, None

        for idx, variant in enumerate(versions):
            variant.setdefault("metadata", {})["ai_review"] = {
                "is_best": idx == ai_review_result.best_version_index,
                "scores": ai_review_result.scores,
                "evaluation": ai_review_result.overall_evaluation if idx == ai_review_result.best_version_index else None,
                "flaws": ai_review_result.critical_flaws if idx == ai_review_result.best_version_index else None,
                "suggestions": ai_review_result.refinement_suggestions if idx == ai_review_result.best_version_index else None,
            }

        return ai_review_result.best_version_index, {
            "best_version_index": ai_review_result.best_version_index,
            "scores": ai_review_result.scores,
            "evaluation": ai_review_result.overall_evaluation,
            "flaws": ai_review_result.critical_flaws,
            "suggestions": ai_review_result.refinement_suggestions,
        }

    async def _revise_with_review_feedback(
        self,
        chapter_content: str,
        *,
        critical_flaws: List[str],
        refinement_suggestions: str,
        chapter_mission: Optional[dict],
        user_id: int,
    ) -> Tuple[str, Dict[str, Any]]:
        """利用 AI 评审的 critical_flaws 和 refinement_suggestions 做定向修订。"""
        if not critical_flaws and not refinement_suggestions:
            return chapter_content, {"applied": False, "reason": "no_feedback"}

        flaws_text = "\n".join(f"- {flaw}" for flaw in critical_flaws) if critical_flaws else "无"
        mission_hint = ""
        if chapter_mission:
            macro_beat = chapter_mission.get("macro_beat_description", "")
            if macro_beat:
                mission_hint = f"\n本章核心任务：{macro_beat}"

        revision_prompt = f"""你是一位资深网文编辑。以下章节已经由评审员指出了关键问题和改进建议。
请根据这些反馈对章节进行定向修订。

**修订原则：**
1. 只修改评审指出的问题，不改变整体情节走向和结构
2. 保持原有字数规模（±10%）
3. 修改要自然融入，不能有明显修补痕迹
4. 保持原文的叙事风格和语气{mission_hint}

[关键缺陷]
{flaws_text}

[改进建议]
{refinement_suggestions or "无"}

[原章节内容]
{chapter_content}

直接输出修改后的完整章节，不要输出其他内容。"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位擅长根据编辑反馈精修文章的网文作者。",
                conversation_history=[{"role": "user", "content": revision_prompt}],
                temperature=0.5,
                user_id=user_id,
                timeout=300.0,
            )
            cleaned = remove_think_tags(response)
            if not cleaned or not cleaned.strip():
                logger.warning("审查反馈修订结果为空，保留原文")
                return chapter_content, {"applied": False, "reason": "empty_response"}

            final = sanitize_chapter_plain_text(cleaned.strip())
            logger.info("审查反馈修订完成: flaws=%d, original_len=%d, revised_len=%d",
                        len(critical_flaws), len(chapter_content), len(final))
            return final, {
                "applied": True,
                "flaws_count": len(critical_flaws),
                "has_suggestions": bool(refinement_suggestions),
            }
        except Exception as exc:
            logger.warning("审查反馈修订失败，保留原文: %s", exc)
            return chapter_content, {"applied": False, "reason": str(exc)}

    async def _run_self_critique(
        self,
        chapter_content: str,
        *,
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        service = SelfCritiqueService(self.session, self.llm_service, self.prompt_service)
        critique = await service.critique_and_revise_loop(
            chapter_content=chapter_content,
            max_iterations=2,
            target_score=80.0,
            dimensions=[
                CritiqueDimension.LOGIC,
                CritiqueDimension.CHARACTER,
                CritiqueDimension.WRITING,
                CritiqueDimension.PACING,
                CritiqueDimension.DIALOGUE,
            ],
            context=context,
            user_id=user_id,
        )
        return critique.get("final_content", chapter_content), {
            "iterations": len(critique.get("iterations", [])),
            "final_score": critique.get("final_score", 0),
            "improvement": critique.get("improvement", 0),
            "status": critique.get("status", "unknown"),
        }

    async def _run_reader_simulation(
        self,
        chapter_content: str,
        *,
        chapter_number: int,
        previous_summary: Optional[str],
        user_id: int,
    ) -> Dict[str, Any]:
        service = ReaderSimulatorService(self.session, self.llm_service, self.prompt_service)
        return await service.simulate_reading_experience(
            chapter_content=chapter_content,
            chapter_number=chapter_number,
            reader_types=[ReaderType.THRILL_SEEKER, ReaderType.CRITIC, ReaderType.CASUAL],
            previous_summary=previous_summary,
            user_id=user_id,
        )

    async def _run_consistency_check(
        self,
        *,
        project_id: str,
        chapter_text: str,
        user_id: int,
    ) -> Tuple[str, Dict[str, Any]]:
        sync_session = getattr(self.session, "sync_session", self.session)
        service = ConsistencyService(sync_session, self.llm_service)
        result = await service.check_consistency(project_id, chapter_text, user_id, include_foreshadowing=True)
        report = {
            "is_consistent": result.is_consistent,
            "summary": result.summary,
            "check_time_ms": result.check_time_ms,
            "violations": [
                {
                    "severity": v.severity.value if hasattr(v.severity, "value") else v.severity,
                    "category": v.category,
                    "description": v.description,
                    "location": v.location,
                    "suggested_fix": v.suggested_fix,
                    "confidence": v.confidence,
                }
                for v in result.violations
            ],
        }

        needs_fix = any(
            v.severity in (ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR)
            for v in result.violations
        )
        if needs_fix:
            fixed = await service.auto_fix(project_id, chapter_text, result.violations, user_id)
            if fixed:
                report["auto_fix_applied"] = True
                return fixed, report

        report["auto_fix_applied"] = False
        return chapter_text, report

    async def _run_optimizer(self, chapter_content: str, *, user_id: int) -> Tuple[str, Dict[str, Any]]:
        prompt_map = {
            "dialogue": "optimize_dialogue",
            "environment": "optimize_environment",
            "psychology": "optimize_psychology",
            "rhythm": "optimize_rhythm",
            "coolpoint": "optimize_coolpoint",
        }

        optimized_content = chapter_content
        notes = []
        for dimension, prompt_name in prompt_map.items():
            prompt = await self.prompt_service.get_prompt(prompt_name)
            if not prompt:
                logger.warning("缺少优化提示词 %s，跳过 %s 维度", prompt_name, dimension)
                continue

            optimize_input = {
                "original_content": optimized_content,
                "additional_notes": "在不改变剧情走向的前提下优化该维度。",
            }
            try:
                response = await self.llm_service.get_llm_response(
                    system_prompt=prompt,
                    conversation_history=[{"role": "user", "content": json.dumps(optimize_input, ensure_ascii=False)}],
                    temperature=0.7,
                    user_id=user_id,
                    timeout=600.0,
                )
                cleaned = remove_think_tags(response)
                if not cleaned:
                    logger.info("优化维度 %s: remove_think_tags 后为空，回退原始响应", dimension)
                    cleaned = response
                normalized = unwrap_markdown_json(cleaned)
                try:
                    parsed = json.loads(normalized)
                except json.JSONDecodeError:
                    try:
                        parsed = json.loads(repair_json(normalized))
                    except json.JSONDecodeError:
                        parsed = None
                if parsed:
                    optimized_content = parsed.get("optimized_content", cleaned)
                    notes.append(
                        {
                            "dimension": dimension,
                            "notes": parsed.get("optimization_notes", "优化完成"),
                        }
                    )
                else:
                    optimized_content = cleaned
                    notes.append({"dimension": dimension, "notes": "优化完成（响应格式非标准JSON）"})
            except Exception as exc:
                logger.warning("优化维度 %s 失败: %s", dimension, exc)

        return optimized_content, {"steps": notes}

    async def _run_enrichment(
        self,
        chapter_content: str,
        *,
        user_id: int,
        target_word_count: int = 3000,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        service = EnrichmentService(self.session, self.llm_service)
        result = await service.check_and_enrich(
            chapter_text=chapter_content,
            target_word_count=target_word_count,
            user_id=user_id,
        )
        if not result:
            return chapter_content, None

        return result.enriched_content, {
            "original_word_count": result.original_word_count,
            "enriched_word_count": result.enriched_word_count,
            "enrichment_ratio": result.enrichment_ratio,
            "enrichment_type": result.enrichment_type,
        }

    async def _run_quality_detection(
        self,
        chapter_content: str,
        *,
        chapter_number: int,
        chapter_mission: Optional[dict],
        previous_chapters_openings: List[str],
        user_id: int,
    ) -> Dict[str, Any]:
        """分析爽点密度和模式重复，返回质量诊断报告（不修改内容）。"""
        opening_300 = chapter_content[:300] if len(chapter_content) > 300 else chapter_content
        ending_300 = chapter_content[-300:] if len(chapter_content) > 300 else chapter_content

        recent_patterns = ""
        if previous_chapters_openings:
            recent_patterns = "\n".join(
                f"第{i+1}个近期章节开头：{op[:200]}"
                for i, op in enumerate(previous_chapters_openings[-3:])
            )

        expected_beat = ""
        if chapter_mission:
            expected_beat = chapter_mission.get("macro_beat_description", "")
            sat_type = chapter_mission.get("satisfaction_design", {}).get("type", "")
            if sat_type:
                expected_beat += f"（爽感类型：{sat_type}）"

        detection_prompt = f"""你是一位资深网文质量分析师。请分析以下章节的两个维度，输出JSON。

## 分析维度

### 1. 爽点密度
检查本章是否有足够的张力/冲突/反转/情绪高潮时刻。
- coolpoint_score (0-10)：爽点密度评分
- coolpoint_moments：列出识别到的爽点/张力时刻（最多5个，每个一句话描述）
- coolpoint_issue：如果评分<6，指出具体问题

### 2. 模式重复
对比本章开头/结尾与近期章节是否存在套路化重复。
- repetition_score (0-10)：独特性评分（10=完全独特，0=严重套路化）
- repetition_issues：发现的重复模式（如"连续3章都以对话开头"、"结尾都用身体反应收束"）
- within_chapter_repetition：章节内部的句式/词汇重复

[本章开头300字]
{opening_300}

[本章结尾300字]
{ending_300}

[本章预期]
{expected_beat or "无特定预期"}

[近期章节开头对比]
{recent_patterns or "无（这是前几章）"}

输出严格JSON格式：
{{"coolpoint_score": 0, "coolpoint_moments": [], "coolpoint_issue": "", "repetition_score": 0, "repetition_issues": [], "within_chapter_repetition": []}}"""

        try:
            response = await self.llm_service.get_llm_response(
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

            logger.info(
                "质量检测完成: chapter=%d coolpoint=%s repetition=%s",
                chapter_number,
                result.get("coolpoint_score"),
                result.get("repetition_score"),
            )
            return result
        except Exception as exc:
            logger.warning("质量检测失败: %s", exc)
            return {"error": str(exc), "coolpoint_score": -1, "repetition_score": -1}

    @staticmethod
    def _build_stage_flags(config: PipelineConfig) -> Dict[str, bool]:
        return {
            "preview": config.enable_preview,
            "optimizer": config.enable_optimizer,
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
        }

    @staticmethod
    def _format_filtered_context(filtered: FilteredContext) -> Optional[str]:
        if not filtered:
            return None

        sections = []
        if filtered.plot_fuel:
            sections.append("## 情节燃料\n" + "\n".join(f"- {item}" for item in filtered.plot_fuel))
        if filtered.character_info:
            sections.append("## 人物维度\n" + "\n".join(f"- {item}" for item in filtered.character_info))
        if filtered.world_fragments:
            sections.append("## 世界碎片\n" + "\n".join(f"- {item}" for item in filtered.world_fragments))
        if filtered.narrative_techniques:
            sections.append("## 叙事技法\n" + "\n".join(f"- {item}" for item in filtered.narrative_techniques))
        if filtered.warnings:
            sections.append("## 冲突警告\n" + "\n".join(f"- {item}" for item in filtered.warnings))

        if not sections:
            return "（未检索到有效上下文）"

        return "\n\n".join(sections)


__all__ = ["PipelineOrchestrator", "PipelineConfig"]
