"""标准分支草稿流式回归：

standard/premium 的草稿流式复用 fast 的 text_delta 管道，但只在
version_count == 1 时开启——多版本并行的 delta 交错到同一条流上是噪音。
本测试用假编排器锁定 VersionGenerationService 的转发/抑制契约。
"""
import asyncio
from types import SimpleNamespace

import pytest

from app.services.version_generation_service import VersionGenerationService


class _FakePolicy:
    def resolve_style_hints(self, enhanced_context, version_count):
        return [None] * version_count


class _FakeSingleGen:
    def __init__(self):
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        return {"content": "正文" * 100, "metadata": {}}


class _FakeOrchestrator:
    def __init__(self):
        self.generation_policy_service = _FakePolicy()
        self.single_version_generation_service = _FakeSingleGen()

    async def _run_ai_review(self, *, versions, chapter_mission, user_id):
        return 0, None


def _run_kwargs(version_count: int, stream_callback):
    return dict(
        prompt_input="写一章",
        prompt_sections=None,
        writer_prompt="system",
        enhanced_context=None,
        version_count=version_count,
        project_id="p1",
        chapter_number=1,
        outline_title="t",
        outline_summary="s",
        chapter_mission=None,
        forbidden_characters=[],
        allowed_new_characters=[],
        user_id=1,
        writer_blueprint={},
        memory_context=None,
        config=SimpleNamespace(enable_two_pass_draft=False, disable_guardrail_rewrite=False),
        chapter_target_word_count=2000,
        chapter_word_count_max=4000,
        genre_profile=None,
        stream_callback=stream_callback,
    )


def test_single_version_forwards_stream_callback():
    orch = _FakeOrchestrator()
    svc = VersionGenerationService(orch)

    async def _cb(delta: str) -> None:
        pass

    result = asyncio.run(svc.run(**_run_kwargs(version_count=1, stream_callback=_cb)))
    assert len(orch.single_version_generation_service.calls) == 1
    assert orch.single_version_generation_service.calls[0]["stream_callback"] is _cb
    assert result["best_version_index"] == 0


def test_multi_version_suppresses_stream_callback():
    orch = _FakeOrchestrator()
    svc = VersionGenerationService(orch)

    async def _cb(delta: str) -> None:
        pass

    asyncio.run(svc.run(**_run_kwargs(version_count=3, stream_callback=_cb)))
    assert len(orch.single_version_generation_service.calls) == 3
    assert all(c["stream_callback"] is None for c in orch.single_version_generation_service.calls)


def test_no_callback_stays_none():
    orch = _FakeOrchestrator()
    svc = VersionGenerationService(orch)
    asyncio.run(svc.run(**_run_kwargs(version_count=1, stream_callback=None)))
    assert orch.single_version_generation_service.calls[0]["stream_callback"] is None
