import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.generation_context_resolution_service import (
    GenerationContextResolutionService,
    ResolvedPrefetchContext,
)


def test_generation_context_resolution_service_reuses_precollected_rag():
    telemetry = SimpleNamespace(emit_rag=AsyncMock())
    service = GenerationContextResolutionService(
        evidence_router=SimpleNamespace(),
        generation_policy_service=SimpleNamespace(resolve_pov_character=lambda mission: None),
        llm_service=SimpleNamespace(),
        session=SimpleNamespace(),
    )

    async def _main():
        prefetch_tasks = SimpleNamespace(
            enhanced_context_task=asyncio.create_task(asyncio.sleep(0, result={"persona": "x"})),
            memory_text_task=asyncio.create_task(asyncio.sleep(0, result="memory")),
            rag_task=None,
            writer_prompt_task=asyncio.create_task(asyncio.sleep(0, result="writer")),
        )
        result = await service.resolve_prefetch_context(
            config=SimpleNamespace(enable_rag=True, rag_mode="simple", rag_retrieval_mode="vector"),
            project_id="proj-1",
            chapter_number=8,
            user_id=1,
            writing_notes="说明",
            chapter_mission=None,
            prefetch_tasks=prefetch_tasks,
            pre_rag_context={"chunks": ["片段"], "summaries": ["摘要"]},
            pre_rag_stats={"source": "pre"},
            history_context={},
            telemetry=telemetry,
        )
        return result

    result = asyncio.run(_main())

    assert isinstance(result, ResolvedPrefetchContext)
    assert result.enhanced_context == {"persona": "x"}
    assert result.project_memory_text == "memory"
    assert result.writer_prompt == "writer"
    assert result.rag_stats["reused"] is True
    telemetry.emit_rag.assert_awaited_once()


def test_generation_context_resolution_service_raises_when_writer_prompt_missing():
    service = GenerationContextResolutionService(
        evidence_router=SimpleNamespace(),
        generation_policy_service=SimpleNamespace(resolve_pov_character=lambda mission: None),
        llm_service=SimpleNamespace(),
        session=SimpleNamespace(),
    )

    async def _main():
        prefetch_tasks = SimpleNamespace(
            enhanced_context_task=None,
            memory_text_task=asyncio.create_task(asyncio.sleep(0, result=None)),
            rag_task=None,
            writer_prompt_task=asyncio.create_task(asyncio.sleep(0, result=None)),
        )
        await service.resolve_prefetch_context(
            config=SimpleNamespace(enable_rag=False, rag_mode="simple", rag_retrieval_mode="vector"),
            project_id="proj-2",
            chapter_number=3,
            user_id=1,
            writing_notes="",
            chapter_mission=None,
            prefetch_tasks=prefetch_tasks,
            pre_rag_context=None,
            pre_rag_stats=None,
            history_context={},
            telemetry=SimpleNamespace(emit_rag=AsyncMock()),
        )

    try:
        asyncio.run(_main())
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 500
    else:
        raise AssertionError("expected HTTPException")
