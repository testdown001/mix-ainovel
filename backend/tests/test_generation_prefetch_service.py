import asyncio
from types import SimpleNamespace

from app.services.generation_prefetch_service import GenerationPrefetchService


class _ImmediateTaskService:
    async def run_with_timeout(self, awaitable, **kwargs):
        return await awaitable


async def _return(value):
    return value


def test_generation_prefetch_service_skips_rag_when_precollected_context_exists():
    service = GenerationPrefetchService(
        async_task_service=_ImmediateTaskService(),
        enhanced_context_service=SimpleNamespace(
            prefetch_enhanced_context=lambda **kwargs: _return({})
        ),
        context_access_service=SimpleNamespace(
            prefetch_project_memory_text=lambda project_id: _return("memory")
        ),
        evidence_router=SimpleNamespace(
            prefetch_local_plot=lambda **kwargs: _return({"chunks": []}),
            prefetch_symbolic_foreshadowing=lambda **kwargs: _return((None, None)),
        ),
        trajectory_analysis_service=SimpleNamespace(
            prefetch_trajectory_context=lambda **kwargs: _return(None)
        ),
        user_style_service=SimpleNamespace(
            prefetch_user_style=lambda user_id: _return((None, None))
        ),
        fingerprint_service=SimpleNamespace(
            prefetch_fingerprint_context=lambda **kwargs: _return(None)
        ),
        writer_prompt_service=SimpleNamespace(
            prefetch_writer_prompt=lambda **kwargs: _return("writer")
        ),
        context_planner=SimpleNamespace(
            build_retrieval_queries=lambda **kwargs: ["query"]
        ),
    )

    async def _main():
        tasks = service.schedule_prefetch_tasks(
            config=SimpleNamespace(
                enable_constitution=False,
                enable_persona=False,
                enable_foreshadowing=False,
                enable_faction=False,
                enable_rag=True,
                rag_mode="simple",
                rag_retrieval_mode="vector",
                enable_trajectory_analysis=False,
                enable_fingerprint=False,
                enable_fast_path=False,
            ),
            project=SimpleNamespace(chapters=[]),
            project_id="proj-1",
            chapter_number=5,
            user_id=1,
            outline_title="标题",
            outline_summary="摘要",
            writing_notes="说明",
            blueprint_dict={"characters": [{"name": "林峰"}]},
            context_plan=SimpleNamespace(),
            history_context={"story_skeleton": "主线"},
            fast_rag_queries=["快查"],
            pre_rag_context={"chunks": ["existing"]},
        )

        assert tasks.rag_task is None
        assert await tasks.memory_text_task == "memory"
        assert await tasks.user_style_task == (None, None)
        assert await tasks.writer_prompt_task == "writer"
        assert await tasks.foreshadowing_task == (None, None)

    asyncio.run(_main())
