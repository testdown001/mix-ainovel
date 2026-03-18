# AIMETA P=安全异步任务_包装asyncio.create_task防止异常静默丢失|R=后台任务管理|E=safe_create_task|X=internal
"""安全的 asyncio.create_task 包装，确保后台任务异常被记录。"""
import asyncio
import logging
from typing import Any, Coroutine, Optional

logger = logging.getLogger(__name__)


def safe_create_task(
    coro: Coroutine[Any, Any, Any],
    *,
    name: Optional[str] = None,
) -> asyncio.Task:
    """创建异步任务并自动捕获/记录未处理异常。

    替代裸 ``asyncio.create_task``，避免后台任务（向量入库、摘要生成等）
    异常被 asyncio 事件循环静默吞掉。
    """

    task = asyncio.create_task(coro, name=name)

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.exception(
                "后台任务 [%s] 异常终止",
                t.get_name(),
                exc_info=exc,
            )

    task.add_done_callback(_on_done)
    return task
