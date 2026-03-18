import asyncio
import logging

from app.services.async_task_service import AsyncTaskService


def test_async_task_service_returns_result():
    service = AsyncTaskService(logging.getLogger("test.async_task"))

    async def _work():
        return {"status": "ok"}

    result = asyncio.run(
        service.run_with_timeout(
            _work(),
            timeout_sec=1,
            task_name="unit_task",
            fallback={"status": "fallback"},
        )
    )

    assert result == {"status": "ok"}


def test_async_task_service_returns_fallback_on_timeout():
    service = AsyncTaskService(logging.getLogger("test.async_task"))

    async def _work():
        await asyncio.sleep(0.02)
        return "late"

    result = asyncio.run(
        service.run_with_timeout(
            _work(),
            timeout_sec=0,
            task_name="timeout_task",
            fallback=("safe", "shape"),
        )
    )

    assert result == ("safe", "shape")


def test_async_task_service_returns_fallback_on_exception():
    service = AsyncTaskService(logging.getLogger("test.async_task"))

    async def _work():
        raise RuntimeError("boom")

    result = asyncio.run(
        service.run_with_timeout(
            _work(),
            timeout_sec=1,
            task_name="error_task",
            fallback=None,
        )
    )

    assert result is None
