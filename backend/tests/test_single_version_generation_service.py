import asyncio
from types import SimpleNamespace

from app.services.single_version_generation_service import SingleVersionGenerationService


VALID_CHAPTER_BODY = (
    "雨声砸在青瓦上，沈砚推开窗，冷风卷着潮气扑进屋内。"
    "街口的灯笼被风吹得一晃一晃，红光落在他的指节上，像一层迟迟不肯退去的血色。"
    "他听见楼下有人压低声音争吵，茶盏碰在桌沿，发出短促的一声响。"
    "那声音让他想起昨夜未写完的信，也想起信尾被墨水洇开的名字。"
)


class _DummyLLM:
    async def get_llm_response(self, **kwargs):
        return VALID_CHAPTER_BODY


class _RetryLLM:
    def __init__(self):
        self.calls = 0

    async def get_llm_response(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return """1.  分析任务：
角色：擅长小说润色的文学编辑。
目标：提升文字的文学性和画面感。
限制：直接输出正文。

2.  原文本分析：
人物：男主，前妻，儿子。
氛围：压抑后反击。
"""
        return VALID_CHAPTER_BODY


class _DummyGuardrails:
    def check(self, **kwargs):
        return SimpleNamespace(passed=True, violations=[])

    def apply_local_patches(self, content, result):
        return content


class _DummyPolicy:
    @staticmethod
    def resolve_temperature(chapter_mission):
        return 0.75


class _DummyCompression:
    async def compress_overlength(self, text, *, target_max, user_id):
        return text[:target_max]


class _DummyPreview:
    async def generate_with_preview(self, **kwargs):
        return {"full_chapter": "预览正文"}


def test_single_version_generation_service_basic_path():
    service = SingleVersionGenerationService(
        llm_service=_DummyLLM(),
        guardrails=_DummyGuardrails(),
        generation_policy_service=_DummyPolicy(),
        text_compression_service=_DummyCompression(),
        preview_generation_service_factory=lambda: _DummyPreview(),
    )

    config = SimpleNamespace(preset="fast", enable_preview=False)
    result = asyncio.run(
        service.generate(
            index=0,
            prompt_input="prompt",
            writer_prompt="writer",
            style_hint=None,
            project_id="proj-1",
            chapter_number=1,
            outline_title="第一章",
            outline_summary="摘要",
            chapter_mission={"pov": "林玄"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            writer_blueprint={},
            memory_context=None,
            enhanced_context=None,
            config=config,
            target_word_count=3000,
            max_word_count=4000,
            genre_profile=None,
        )
    )

    assert result["content"] == VALID_CHAPTER_BODY
    assert result["metadata"]["resolved_temperature"] == 0.75


def test_completion_token_budget_is_anchored_to_target_not_maximum():
    budget = SingleVersionGenerationService.resolve_completion_token_budget(
        target_word_count=3000,
        max_word_count=4000,
        configured_max_tokens=16384,
    )

    assert budget == 3600
    assert budget < int(4000 * 1.5)


def test_single_version_generation_retries_when_model_returns_prompt_analysis():
    llm = _RetryLLM()
    service = SingleVersionGenerationService(
        llm_service=llm,
        guardrails=_DummyGuardrails(),
        generation_policy_service=_DummyPolicy(),
        text_compression_service=_DummyCompression(),
        preview_generation_service_factory=lambda: _DummyPreview(),
    )

    config = SimpleNamespace(preset="standard", enable_preview=False)
    result = asyncio.run(
        service.generate(
            index=0,
            prompt_input="prompt",
            writer_prompt="writer",
            style_hint=None,
            project_id="proj-1",
            chapter_number=1,
            outline_title="第一章",
            outline_summary="摘要",
            chapter_mission={"pov": "林玄"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            writer_blueprint={},
            memory_context=None,
            enhanced_context=None,
            config=config,
            target_word_count=3000,
            max_word_count=4000,
            genre_profile=None,
        )
    )

    assert llm.calls == 2
    assert result["metadata"]["invalid_output_retry"] is True
    assert result["content"].startswith("雨声砸在青瓦上")
    assert "分析任务" not in result["content"]
