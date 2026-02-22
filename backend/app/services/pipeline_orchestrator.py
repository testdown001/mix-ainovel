# AIMETA P=写作流水线编排_统一生成入口|R=上下文汇聚_生成_审查_优化|NR=不含API路由|E=PipelineOrchestrator|X=internal|A=编排器|D=fastapi,sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.constants import CHAPTER_MAX_WORDS
from ..repositories.system_config_repository import SystemConfigRepository
from ..services.chapter_guardrails import default_guardrails
from ..services.enhanced_writing_flow import EnhancedWritingFlow
from ..services.llm_service import LLMService
from ..services.novel_service import NovelService
from ..services.preview_generation_service import PreviewGenerationService
from ..services.prompt_service import PromptService
from ..services.writer_context_builder import default_context_builder
from ..services.writer_shared import (
    build_blueprint_constraints_for_mission,
    generate_chapter_mission as _shared_generate_chapter_mission,
    normalize_blueprint_relationships,
    rewrite_with_guardrails as _shared_rewrite_with_guardrails,
)
from ..services.platinum_writing_context import (
    PLATINUM_WRITING_BRIEF_FALLBACK,
    build_foreshadowing_urgency_brief,
    build_hook_continuity_brief,
    build_platinum_rhythm_brief,
)
from ..utils.json_utils import remove_think_tags, sanitize_chapter_plain_text, unwrap_markdown_json

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
    enable_fingerprint: bool = False
    enable_polish: bool = False


class PipelineOrchestrator(PipelineContextMixin, PipelinePromptMixin, PipelineReviewMixin):
    """统一写作流水线编排器。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.novel_service = NovelService(session)
        self.context_builder = default_context_builder
        self.guardrails = default_guardrails

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
        blueprint_dict = normalize_blueprint_relationships(project_schema.blueprint.model_dump())

        outline_title = outline.title or f"第{outline.chapter_number}章"
        outline_summary = outline.summary or "暂无摘要"
        writing_notes = writing_notes or "无额外写作指令"

        all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

        pattern_constraint = self._build_pattern_differentiation(
            history_context.get("completed_chapters", [])
        )

        pre_visibility_context = self.context_builder.build_visibility_context(
            blueprint=blueprint_dict,
            completed_summaries=history_context["completed_summaries"],
            previous_tail=history_context["previous_tail"],
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            allowed_new_characters=[],
        )
        introduced_characters_for_mission = pre_visibility_context["introduced_characters"]
        blueprint_constraints = build_blueprint_constraints_for_mission(
            blueprint_dict=blueprint_dict,
            outline_title=outline_title,
            outline_summary=outline_summary,
        )

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
        emotion_expression_brief = self._build_emotion_expression_brief(
            history_context.get("completed_chapters", [])
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

        # ---- 用户写作风格偏好 ----
        user_style_rules: Optional[str] = None
        try:
            from sqlalchemy import select as sa_select
            from ..models.user_writing_preference import UserWritingPreference
            from ..core.writing_style_presets import build_user_style_prompt
            result = await self.session.execute(
                sa_select(UserWritingPreference).where(UserWritingPreference.user_id == user_id)
            )
            pref = result.scalars().first()
            if pref:
                user_style_rules = build_user_style_prompt(pref)
                logger.info("用户 %s 已加载写作风格偏好 (preset=%s)", user_id, pref.style_preset)
        except Exception as e:
            logger.warning("加载用户写作风格偏好失败（不影响生成）: %s", e)

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

            # ========== 阶段 A：顺序执行修改 best_content 的步骤 ==========

            if ai_review_result and (ai_review_result.get("flaws") or ai_review_result.get("suggestions")):
                best_content, revision_report = await self._revise_with_review_feedback(
                    best_content,
                    critical_flaws=ai_review_result.get("flaws") or [],
                    refinement_suggestions=ai_review_result.get("suggestions") or "",
                    chapter_mission=chapter_mission,
                    user_id=user_id,
                )
                review_summaries["review_driven_revision"] = revision_report

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

            if config.enable_consistency:
                best_content, consistency_report = await self._run_consistency_check(
                    project_id=project_id,
                    chapter_text=best_content,
                    user_id=user_id,
                )
                review_summaries["consistency"] = consistency_report

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

            if config.enable_polish:
                best_content, polish_report = await self._run_polish(best_content, user_id=user_id)
                review_summaries["polish"] = polish_report

            if config.enable_enrichment:
                best_content, enrichment_report = await self._run_enrichment(
                    best_content,
                    user_id=user_id,
                )
                if enrichment_report:
                    review_summaries["enrichment"] = enrichment_report

            # ========== 阶段 B：并行执行只读分析步骤 ==========

            async def _do_six_dimension() -> None:
                if not (enhanced_flow and config.enable_six_dimension):
                    return
                result = await enhanced_flow.post_generation_review(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_title=outline_title,
                    chapter_content=best_content,
                    chapter_plan=json.dumps(chapter_mission, ensure_ascii=False) if chapter_mission else None,
                    previous_summary=history_context["previous_summary"],
                )
                review_summaries["enhanced_review"] = result

            async def _do_reader_simulation() -> None:
                if not config.enable_reader_sim:
                    return
                feedback = await self._run_reader_simulation(
                    best_content,
                    chapter_number=chapter_number,
                    previous_summary=history_context["previous_summary"],
                    user_id=user_id,
                )
                review_summaries["reader_simulator"] = feedback

            async def _do_anti_hallucination() -> None:
                if not config.enable_anti_hallucination:
                    return
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

            async def _do_quality_detection() -> None:
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

            await asyncio.gather(
                _do_six_dimension(),
                _do_reader_simulation(),
                _do_anti_hallucination(),
                _do_quality_detection(),
            )

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

        if preset == "platinum":
            config.enable_memory = True
            config.enable_six_dimension = True
            config.enable_self_critique = True
            config.enable_reader_sim = True
            config.enable_consistency = True
            config.enable_enrichment = True
            config.enable_polish = True

        if preset == "basic":
            config.enable_rag = True

        for key in (
            "enable_preview",
            "enable_optimizer",
            "enable_consistency",
            "enable_enrichment",
            "async_finalize",
            "enable_rag",
            "enable_polish",
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
                max_tokens=settings.writer_max_tokens,
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
                violations_text = self.guardrails.format_violations_for_rewrite(recheck_result)
                content = await _shared_rewrite_with_guardrails(
                    self.llm_service,
                    self.prompt_service,
                    original_text=locally_patched,
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

    @staticmethod
    def _build_stage_flags(config: PipelineConfig) -> Dict[str, bool]:
        return {
            "preview": config.enable_preview,
            "optimizer": config.enable_optimizer,
            "polish": config.enable_polish,
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


__all__ = ["PipelineOrchestrator", "PipelineConfig"]
