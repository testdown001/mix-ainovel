import asyncio

from app.services.batch_generation_service import BatchGenerationService


def test_batch_generation_service_build_dependency_map():
    chapter_numbers = [3, 4, 6, 7]
    existing_generated = {1, 2, 5}

    dependencies = BatchGenerationService._build_dependency_map(chapter_numbers, existing_generated)

    assert dependencies[3] is None
    assert dependencies[4] == 3
    assert dependencies[6] is None
    assert dependencies[7] == 6


def test_batch_generation_service_empty_input_returns_empty_map():
    dependencies = BatchGenerationService._build_dependency_map([], {1, 2})
    assert dependencies == {}


def test_dependency_aware_scheduler_runs_independent_chains_in_parallel():
    active = 0
    max_active = 0
    started: list[int] = []
    completed: list[int] = []

    async def _generate(chapter_number: int):
        nonlocal active, max_active
        started.append(chapter_number)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"chapter_number": chapter_number, "status": "success"}

    async def _completed(chapter_number, _result, _processed, _total):
        completed.append(chapter_number)

    results = asyncio.run(
        BatchGenerationService.run_dependency_aware(
            chapter_numbers=[3, 4, 6, 7],
            existing_generated={1, 2, 5},
            parallel_workers=2,
            generate_one=_generate,
            on_completed=_completed,
        )
    )

    assert max_active == 2
    assert set(started[:2]) == {3, 6}
    assert started.index(4) > started.index(3)
    assert started.index(7) > started.index(6)
    assert set(completed) == {3, 4, 6, 7}
    assert [item["chapter_number"] for item in results] == [3, 4, 6, 7]


def test_dependency_aware_scheduler_keeps_contiguous_chapters_serial():
    active = 0
    max_active = 0
    started: list[int] = []

    async def _generate(chapter_number: int):
        nonlocal active, max_active
        started.append(chapter_number)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return {"chapter_number": chapter_number, "status": "success"}

    asyncio.run(
        BatchGenerationService.run_dependency_aware(
            chapter_numbers=[7, 8, 9],
            existing_generated={1, 2, 3, 4, 5, 6},
            parallel_workers=8,
            generate_one=_generate,
        )
    )

    assert max_active == 1
    assert started == [7, 8, 9]


def test_dependency_aware_scheduler_cancels_running_children():
    cancelled: list[int] = []

    async def _generate(chapter_number: int):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(chapter_number)
            raise

    async def _run():
        task = asyncio.create_task(
            BatchGenerationService.run_dependency_aware(
                chapter_numbers=[3, 6],
                existing_generated={1, 2, 5},
                parallel_workers=2,
                generate_one=_generate,
            )
        )
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())

    assert set(cancelled) == {3, 6}
