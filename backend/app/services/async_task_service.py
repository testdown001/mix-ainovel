# AIMETA P=异步任务服务_超时与降级控制|R=并发任务超时包装|NR=不含业务逻辑|E=AsyncTaskService|X=internal|A=并发控制|D=asyncio|S=compute|RD=./README.ai
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable


class AsyncTaskService:
    """统一处理异步任务超时、异常和降级返回值。"""

    def __init__(self, logger_: logging.Logger | None = None):
        self.logger = logger_ or logging.getLogger(__name__)

    async def run_with_timeout(
        self,
        awaitable: Awaitable[Any],
        *,
        timeout_sec: int,
        task_name: str,
        fallback: Any = None,
    ) -> Any:
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_sec)
        except asyncio.TimeoutError:
            self.logger.warning("并行任务超时: %s (timeout=%ss)", task_name, timeout_sec)
            return fallback
        except Exception as exc:
            self.logger.warning("并行任务失败: %s, error=%s", task_name, exc)
            return fallback
