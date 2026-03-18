import asyncio
from types import SimpleNamespace

from app.services.generation_prompt_context_service import (
    GenerationPromptContextService,
    PromptContextInputs,
)


def test_generation_prompt_context_service_await_mission_brief_returns_none_on_failure():
    service = GenerationPromptContextService(
        prompt_service=SimpleNamespace(),
        context_access_service=SimpleNamespace(),
        prompt_assembly_service=SimpleNamespace(),
    )

    async def _main():
        async def _boom():
            raise RuntimeError("x")

        return await service.await_mission_brief(asyncio.create_task(_boom()))

    result = asyncio.run(_main())
    assert result is None


def test_generation_prompt_context_service_resolves_prompt_inputs(monkeypatch):
    from app.services import generation_prompt_context_service as module

    monkeypatch.setattr(
        module,
        "build_platinum_rhythm_brief",
        lambda **kwargs: "节奏简报",
    )
    monkeypatch.setattr(
        module,
        "build_hook_continuity_brief",
        lambda **kwargs: "钩子简报",
    )

    class _GenreProfileService:
        @staticmethod
        def get_profile(name):
            return {"name": name, "pacing_config": {"quest_ratio": 0.5}}

        @staticmethod
        def build_genre_prompt_injection(profile):
            return "题材约束"

    class _StrandWeaveService:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def plan_strands(self):
            return None

        def get_chapter_strand(self, chapter_number):
            return {"chapter_number": chapter_number, "strand": "quest"}

    monkeypatch.setattr(module, "settings", SimpleNamespace(
        enable_genre_adaptation=True,
        strand_quest_ratio=0.4,
        strand_fire_ratio=0.3,
        strand_constellation_ratio=0.3,
        strand_interleave_interval=3,
    ))
    monkeypatch.setitem(__import__("sys").modules, "app.services.genre_profile_service", SimpleNamespace(GenreProfileService=_GenreProfileService))
    monkeypatch.setitem(__import__("sys").modules, "app.services.strand_weave_service", SimpleNamespace(StrandWeaveService=_StrandWeaveService))

    prompt_service = SimpleNamespace(get_prompt=lambda name: asyncio.sleep(0, result="白金简报"))
    prompt_assembly_service = SimpleNamespace(
        build_emotion_expression_brief=lambda completed: "情绪约束"
    )
    context_access_service = SimpleNamespace()
    service = GenerationPromptContextService(
        prompt_service=prompt_service,
        context_access_service=context_access_service,
        prompt_assembly_service=prompt_assembly_service,
    )

    async def _main():
        return await service.resolve_prompt_context_inputs(
            config=SimpleNamespace(pacing_model="strand_weave"),
            project=SimpleNamespace(outlines=[SimpleNamespace(chapter_number=12)]),
            chapter_number=10,
            outline_title="标题",
            outline_summary="摘要",
            chapter_mission={},
            history_context={"previous_summary": "上章", "previous_tail": "尾巴", "completed_chapters": []},
            blueprint_dict={"genre": "都市"},
        )

    result = asyncio.run(_main())

    assert isinstance(result, PromptContextInputs)
    assert result.total_chapters == 12
    assert result.platinum_writing_brief == "白金简报"
    assert result.genre_prompt_injection == "题材约束"
    assert result.platinum_rhythm_brief == "节奏简报"
    assert result.hook_continuity_brief == "钩子简报"
    assert result.emotion_expression_brief == "情绪约束"
