# AIMETA P=生成Prompt阶段服务_段落装配与预算整理|R=Prompt组装_文学附加约束|NR=不含主流程编排|E=GenerationPromptStageService|X=internal|A=Prompt阶段|D=json|S=compute|RD=./README.ai
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .reference_prose_service import ReferenceProseService

logger = logging.getLogger(__name__)


@dataclass
class PromptStageResult:
    prompt_sections: list[tuple[str, str]]
    prompt_compile_summary: Dict[str, Any]
    prompt_input: str
    writer_prompt: str
    reference_prose_text: str = ""
    fusion_dna_text: str = ""


class GenerationPromptStageService:
    """统一构建生成前的 prompt sections 与最终 prompt 输入。"""

    def __init__(
        self,
        *,
        prompt_assembly_service,
        prompt_compiler,
        prompt_service,
        enhanced_context_service,
    ):
        self.prompt_assembly_service = prompt_assembly_service
        self.prompt_compiler = prompt_compiler
        self.prompt_service = prompt_service
        self.enhanced_context_service = enhanced_context_service

    async def build_prompt_stage(
        self,
        *,
        config: Any,
        context_plan: Any,
        writer_prompt: str,
        writer_blueprint: Dict[str, Any],
        history_context: Dict[str, Any],
        chapter_mission: Optional[dict],
        mission_brief_text: Optional[str],
        rag_context: Optional[Dict[str, Any]],
        knowledge_context: Optional[str],
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        forbidden_characters: list[str],
        project_memory_text: Optional[str],
        memory_context: Optional[str],
        platinum_writing_brief: Optional[str],
        platinum_rhythm_brief: Optional[str],
        foreshadowing_urgency_brief: Optional[str],
        hook_continuity_brief: Optional[str],
        emotion_expression_brief: Optional[str],
        genre_prompt_injection: Optional[str],
        fingerprint_context: Optional[str],
        prediction_text: Optional[str],
        user_style_rules: Optional[str],
        chapter_word_count_min: int,
        chapter_word_count_max: int,
        chapter_target_word_count: int,
        chapter_state_context: Optional[str],
        coolpoint_rhythm_directive: Optional[str],
        writing_strategy: Any,
        power_system_context: Optional[str],
        relationship_context: Optional[str],
        trajectory_context: Optional[str],
        project: Any,
        chapter_number: int,
        project_reference_novels: Any,
        reference_service: Any,
        enhanced_context: Dict[str, Any],
    ) -> PromptStageResult:
        prompt_sections = self.prompt_assembly_service.build_prompt_sections(
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
            chapter_state_context=chapter_state_context,
            coolpoint_rhythm_directive=coolpoint_rhythm_directive,
            writing_strategy=writing_strategy,
            power_system_context=power_system_context,
            relationship_context=relationship_context,
            trajectory_context=trajectory_context,
        )
        prompt_sections, prompt_compile_summary = self.prompt_compiler.compile(
            plan=context_plan,
            sections=prompt_sections,
        )

        reference_prose_text = ""
        if config.enable_reference_prose:
            try:
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
            except Exception as exc:
                logger.warning("范文注入失败（不影响生成）: %s", exc)

        fusion_dna_text = ""
        if hasattr(project, "fusion_dna") and project.fusion_dna:
            fusion_dna_text = reference_service.format_fusion_dna_for_prompt(project.fusion_dna)
            if fusion_dna_text:
                prompt_sections.append(("[创作DNA融合指引]", fusion_dna_text))

        if config.enable_narrative_variety:
            try:
                from .narrative_variety_tracker import ChapterPattern, NarrativeVarietyTracker

                recent_patterns = []
                for chapter in sorted(project.chapters, key=lambda item: item.chapter_number):
                    if chapter.chapter_number < chapter_number and chapter.selected_version:
                        chapter_mission_data = (chapter.selected_version.metadata_ or {}).get("chapter_mission")
                        pattern = ChapterPattern.from_mission_and_text(
                            chapter.chapter_number,
                            chapter_mission_data,
                            chapter.selected_version.content,
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
            except Exception as exc:
                logger.warning("叙事多样性追踪失败（不影响生成）: %s", exc)

        if enhanced_context:
            prompt_sections = self.enhanced_context_service.build_prompt_sections(
                prompt_sections,
                enhanced_context,
            )

        from .prompt_budget_manager import PromptBudgetManager

        budget_manager = PromptBudgetManager()
        prompt_sections = budget_manager.apply_budget(prompt_sections)
        prompt_sections = budget_manager.reorder_for_cache(prompt_sections)
        prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)

        final_writer_prompt = writer_prompt
        if config.use_slim_prompt:
            slim_prompt = await self.prompt_service.get_prompt("writing_v3")
            if slim_prompt:
                final_writer_prompt = slim_prompt

        return PromptStageResult(
            prompt_sections=prompt_sections,
            prompt_compile_summary=prompt_compile_summary,
            prompt_input=prompt_input,
            writer_prompt=final_writer_prompt,
            reference_prose_text=reference_prose_text,
            fusion_dna_text=fusion_dna_text,
        )
