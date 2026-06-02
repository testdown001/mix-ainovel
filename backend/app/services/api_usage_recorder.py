# AIMETA P=API用量记录_可移植upsert与token估算|R=按天累加model+api_type用量|E=record_usage,estimate_tokens|X=internal|A=服务函数|D=sqlalchemy|S=db
"""API 用量记录工具。

设计要点（对齐项目 MySQL/SQLite 双后端）：
- **可移植 upsert**：不使用 PostgreSQL 专用的 ``insert().on_conflict_do_update``，
  改为「先 UPDATE，命中 0 行则 INSERT，遇唯一约束冲突回退再 UPDATE」，MySQL/SQLite 通用。
- **token 估算**：流式补全无法稳定拿到精确 usage，按中英混合启发式估算
  （CJK 字符 ≈ 1 token，其余 ≈ 1 token / 4 字符）。请求次数为精确计数。
  embedding 等非流式接口若返回真实 usage，由调用方传入精确值覆盖估算。
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.api_usage_log import ApiUsageLog

logger = logging.getLogger(__name__)


def estimate_tokens(text: Optional[str]) -> int:
    """中英混合文本的 token 粗估：CJK≈1/字，其余≈1/4字符。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    other = len(text) - cjk
    return int(cjk + other / 4) + 1


async def record_usage(
    session: AsyncSession,
    *,
    model: Optional[str],
    api_type: str = "default",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    request_count: int = 1,
    log_date: Optional[_date] = None,
) -> None:
    """按 (log_date, model, api_type) 累加一条用量记录（MySQL/SQLite 通用 upsert）。"""
    model = model or "unknown"
    day = log_date or _date.today()

    upd = (
        update(ApiUsageLog)
        .where(
            ApiUsageLog.log_date == day,
            ApiUsageLog.model == model,
            ApiUsageLog.api_type == api_type,
        )
        .values(
            prompt_tokens=ApiUsageLog.prompt_tokens + prompt_tokens,
            completion_tokens=ApiUsageLog.completion_tokens + completion_tokens,
            request_count=ApiUsageLog.request_count + request_count,
        )
    )
    result = await session.execute(upd)
    if (result.rowcount or 0) > 0:
        await session.commit()
        return

    # 不存在则插入；并发下可能撞唯一约束 → 回退为 UPDATE
    session.add(
        ApiUsageLog(
            log_date=day,
            model=model,
            api_type=api_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            request_count=request_count,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await session.execute(upd)
        await session.commit()
