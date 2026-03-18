import asyncio
from types import SimpleNamespace

from app.services.single_version_generation_service import SingleVersionGenerationService


class _DummyLLM:
    async def get_llm_response(self, **kwargs):
        return "正文内容"


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

    assert result["content"] == "正文内容"
    assert result["metadata"]["resolved_temperature"] == 0.75
