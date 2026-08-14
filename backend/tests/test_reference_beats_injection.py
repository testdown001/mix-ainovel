"""[参考桥段] 段的注入条件与降级。

契约：enable_reference_beats（standard+ 默认开）且项目绑定了参考小说才注入；
选取/嵌入任何失败只记日志不影响生成；未传 llm_service 的旧调用方自动跳过。
"""
import asyncio
from datetime import datetime
from types import SimpleNamespace

from app.services.generation_prompt_stage_service import GenerationPromptStageService


def _build_service(llm_service):
    return GenerationPromptStageService(
        prompt_assembly_service=SimpleNamespace(
            build_prompt_sections=lambda **kwargs: [("[基础]", "基础内容")]
        ),
        prompt_compiler=SimpleNamespace(
            compile=lambda **kwargs: ([("[基础]", "基础内容")], {})
        ),
        prompt_service=SimpleNamespace(get_prompt=lambda name: asyncio.sleep(0, result=None)),
        enhanced_context_service=SimpleNamespace(
            build_prompt_sections=lambda sections, ctx: sections
        ),
        llm_service=llm_service,
    )


def _novel_with_beats():
    return SimpleNamespace(
        id=1,
        title="参考书",
        updated_at=datetime(2026, 1, 1),
        beat_library={
            "beats": [
                {
                    "name": "当众对峙·反转",
                    "situation": "主角与宿敌当众对峙",
                    "tags": ["对峙"],
                    "setup": "三章铺垫",
                    "turn": "伏笔回收",
                    "payoff": "旁观者态度翻转",
                    "pitfalls": "铺垫不足会显得突兀",
                }
            ],
            "structure": {},
        },
    )


def _run(service, *, enable_beats, novels, mission=None):
    async def _main():
        return await service.build_prompt_stage(
            config=SimpleNamespace(
                enable_reference_prose=False,
                enable_reference_beats=enable_beats,
                enable_narrative_variety=False,
                use_slim_prompt=False,
            ),
            context_plan=SimpleNamespace(),
            writer_prompt="BASE",
            writer_blueprint={},
            history_context={"previous_summary": "", "previous_tail": "", "story_skeleton": ""},
            chapter_mission=mission or {"goal": "公开对峙分出胜负"},
            mission_brief_text=None,
            rag_context=None,
            outline_title="第9章 对峙",
            outline_summary="主角与宿敌摊牌",
            writing_notes="",
            forbidden_characters=[],
            project_memory_text=None,
            memory_context=None,
            platinum_writing_brief=None,
            platinum_rhythm_brief=None,
            foreshadowing_urgency_brief=None,
            hook_continuity_brief=None,
            emotion_expression_brief=None,
            genre_prompt_injection=None,
            fingerprint_context=None,
            prediction_text=None,
            user_style_rules=None,
            chapter_word_count_min=1000,
            chapter_word_count_max=2000,
            chapter_target_word_count=1500,
            chapter_state_context=None,
            coolpoint_rhythm_directive=None,
            writing_strategy=SimpleNamespace(warnings=[]),
            power_system_context=None,
            relationship_context=None,
            trajectory_context=None,
            outline_revision_context=None,
            project=SimpleNamespace(chapters=[], fusion_dna=None),
            chapter_number=9,
            project_reference_novels=novels,
            reference_service=SimpleNamespace(
                format_style_samples_for_prompt=lambda novels: "",
                format_memory_card_for_prompt=lambda novels: "",
                format_fusion_dna_for_prompt=lambda dna: "",
            ),
            enhanced_context={},
        )

    return asyncio.run(_main())


class _LLM:
    async def get_embeddings_batch(self, texts, **_kw):
        return [[1.0, 0.0] for _ in texts]


def test_beats_injected_when_enabled_with_novels():
    result = _run(_build_service(_LLM()), enable_beats=True, novels=[_novel_with_beats()])
    assert "[参考桥段]" in result.prompt_input
    assert "当众对峙·反转" in result.prompt_input
    assert "伏笔回收" in result.prompt_input


def test_beats_skipped_when_disabled():
    result = _run(_build_service(_LLM()), enable_beats=False, novels=[_novel_with_beats()])
    assert "[参考桥段]" not in result.prompt_input


def test_beats_skipped_without_reference_novels():
    result = _run(_build_service(_LLM()), enable_beats=True, novels=[])
    assert "[参考桥段]" not in result.prompt_input


def test_beats_skipped_without_llm_service():
    # 旧调用方（未传 llm_service）不加段也不报错
    result = _run(_build_service(None), enable_beats=True, novels=[_novel_with_beats()])
    assert "[参考桥段]" not in result.prompt_input


def test_beat_selection_failure_does_not_break_generation():
    class _Boom:
        async def get_embeddings_batch(self, texts, **_kw):
            raise RuntimeError("嵌入通道故障")

    # 嵌入炸了 → 回退关键词打分；桥段只有 1 条 ≤ top_k 直接返回，无论哪条路都不该抛
    result = _run(_build_service(_Boom()), enable_beats=True, novels=[_novel_with_beats()])
    assert "基础内容" in result.prompt_input


def test_old_data_without_beat_library_noop():
    novel = SimpleNamespace(id=2, title="老书", updated_at=None, beat_library=None)
    result = _run(_build_service(_LLM()), enable_beats=True, novels=[novel])
    assert "[参考桥段]" not in result.prompt_input
