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
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta
from typing import Optional

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.api_usage_log import ApiUsageLog
from ..models.llm_call_log import LLMCallLog

logger = logging.getLogger(__name__)

# LLM 调用遥测保留窗口 + 定期清理触发间隔（每 N 次写入清理一次过期行）
_LLM_CALL_LOG_RETENTION_DAYS = 7
_LLM_CALL_LOG_PRUNE_EVERY = 300
_llm_call_log_counter = 0


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


async def record_call_log(
    session: AsyncSession,
    *,
    api_type: str = "default",
    model: Optional[str] = None,
    host: Optional[str] = None,
    status: str = "success",
    latency_ms: int = 0,
    http_status: Optional[int] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    user_id: Optional[int] = None,
) -> None:
    """记录一次 LLM 调用遥测（通道/模型/延迟/状态/错误），供后台「通道诊断」排查
    生成慢/报错/超时。每 N 次写入顺带清理超过保留窗口的旧行。"""
    global _llm_call_log_counter
    session.add(
        LLMCallLog(
            api_type=(api_type or "default")[:32],
            model=(model or "")[:128],
            host=(host or "")[:256],
            status=(status or "success")[:16],
            latency_ms=int(latency_ms or 0),
            http_status=http_status if isinstance(http_status, int) else None,
            error_type=(error_type[:64] if error_type else None),
            error_message=(error_message[:512] if error_message else None),
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
            user_id=user_id,
        )
    )
    await session.commit()

    _llm_call_log_counter += 1
    if _llm_call_log_counter % _LLM_CALL_LOG_PRUNE_EVERY == 0:
        cutoff = _datetime.utcnow() - _timedelta(days=_LLM_CALL_LOG_RETENTION_DAYS)
        try:
            await session.execute(delete(LLMCallLog).where(LLMCallLog.created_at < cutoff))
            await session.commit()
        except Exception as exc:  # pragma: no cover - 清理失败不影响记录
            await session.rollback()
            logger.warning("清理过期 LLM 调用遥测失败(已忽略): %s", exc)
