import asyncio
from types import SimpleNamespace

from app.services.generation_prompt_stage_service import (
    GenerationPromptStageService,
    PromptStageResult,
)


def test_generation_prompt_stage_service_returns_prompt_input_and_overrides_writer_prompt(monkeypatch):
    from app.services import generation_prompt_stage_service as module

    monkeypatch.setattr(
        module.ReferenceProseService,
        "select_references",
        lambda *args, **kwargs: ["ref"],
    )
    monkeypatch.setattr(
        module.ReferenceProseService,
        "format_for_prompt",
        lambda refs: "范文片段" if refs else "",
    )

    prompt_assembly_service = SimpleNamespace(
        build_prompt_sections=lambda **kwargs: [("[基础]", "基础内容")]
    )
    prompt_compiler = SimpleNamespace(
        compile=lambda **kwargs: ([("[基础]", "基础内容")], {"compiled": True})
    )
    prompt_service = SimpleNamespace(
        get_prompt=lambda name: asyncio.sleep(0, result="SLIM" if name == "writing_v3" else None)
    )
    enhanced_context_service = SimpleNamespace(
        build_prompt_sections=lambda sections, ctx: sections + [("[增强]", "增强内容")]
    )

    service = GenerationPromptStageService(
        prompt_assembly_service=prompt_assembly_service,
        prompt_compiler=prompt_compiler,
        prompt_service=prompt_service,
        enhanced_context_service=enhanced_context_service,
    )

    async def _main():
        return await service.build_prompt_stage(
            config=SimpleNamespace(
                enable_reference_prose=True,
                enable_narrative_variety=False,
                use_slim_prompt=True,
            ),
            context_plan=SimpleNamespace(),
            writer_prompt="BASE",
            writer_blueprint={},
            history_context={"previous_summary": "", "previous_tail": "", "story_skeleton": ""},
            chapter_mission={},
            mission_brief_text="任务书",
            rag_context=None,
            knowledge_context=None,
            outline_title="标题",
            outline_summary="摘要",
            writing_notes="说明",
            forbidden_characters=[],
            project_memory_text=None,
            memory_context=None,
            platinum_writing_brief="白金",
            platinum_rhythm_brief="节奏",
            foreshadowing_urgency_brief=None,
            hook_continuity_brief="钩子",
            emotion_expression_brief="情绪",
            genre_prompt_injection="题材",
            fingerprint_context="指纹",
            prediction_text="推演",
            user_style_rules="风格",
            chapter_word_count_min=1000,
            chapter_word_count_max=2000,
            chapter_target_word_count=1500,
            chapter_state_context=None,
            coolpoint_rhythm_directive=None,
            writing_strategy=SimpleNamespace(
                style_weight=1.0,
                reference_weight=1.0,
                genre_weight=1.0,
                warnings=[],
            ),
            power_system_context=None,
            relationship_context=None,
            trajectory_context=None,
            project=SimpleNamespace(chapters=[], fusion_dna={"style_fingerprint": "冷硬"}),
            chapter_number=9,
            project_reference_novels=[SimpleNamespace()],
            reference_service=SimpleNamespace(
                format_style_samples_for_prompt=lambda novels: "风格样本",
                format_memory_card_for_prompt=lambda novels: "记忆卡",
                format_fusion_dna_for_prompt=lambda fusion_dna: "融合DNA",
            ),
            enhanced_context={"writer_persona": "人格"},
        )

    result = asyncio.run(_main())

    assert isinstance(result, PromptStageResult)
    assert result.writer_prompt == "SLIM"
    assert "基础内容" in result.prompt_input
    assert result.reference_prose_text == "范文片段"
    assert result.fusion_dna_text == "融合DNA"
