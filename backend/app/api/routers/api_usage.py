# AIMETA P=API用量管理_token消耗统计与记录|R=用量日志查询_记录|E=route:/api/api-usage/*|X=http|A=用量统计|D=fastapi|S=db
import logging
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin
from ...db.session import get_session
from ...models.api_usage_log import ApiUsageLog
from ...schemas.user import UserInDB
from ...services.api_usage_recorder import record_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/api-usage", tags=["ApiUsage"])


# ---- Schemas ----

class ApiUsageRecord(BaseModel):
    model: str
    api_type: str = "default"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    request_count: int = 1


class ApiUsageRow(BaseModel):
    log_date: date
    model: str
    api_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_count: int


class ModelSummary(BaseModel):
    model: str
    api_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_count: int


class ApiUsageStats(BaseModel):
    period: str
    start_date: date
    end_date: date
    rows: List[ApiUsageRow]
    summary: List[ModelSummary]
    grand_total_tokens: int
    grand_total_requests: int


# ---- Endpoints ----

@router.post("/record", status_code=204)
async def record_usage_endpoint(
    payload: ApiUsageRecord,
    session: AsyncSession = Depends(get_session),
):
    """记录一次 API 调用的 token 消耗（内部/外部 worker 调用）。"""
    await record_usage(
        session,
        model=payload.model,
        api_type=payload.api_type,
        prompt_tokens=payload.prompt_tokens,
        completion_tokens=payload.completion_tokens,
        request_count=payload.request_count,
    )


@router.get("/stats", response_model=ApiUsageStats)
async def get_usage_stats(
    period: str = Query("week", pattern="^(day|week|month|custom)$"),
    start_date: Optional[date] = Query(None, description="自定义起始日期（period=custom 时生效）"),
    end_date: Optional[date] = Query(None, description="自定义结束日期（period=custom 时生效）"),
    session: AsyncSession = Depends(get_session),
    _admin: UserInDB = Depends(get_current_admin),
):
    """查询 API 用量统计（管理员）。period=day|week|month|custom；custom 需配合 start_date/end_date。"""
    today = date.today()
    if period == "custom" and start_date and end_date:
        start, end = start_date, end_date
        if start > end:
            start, end = end, start
    else:
        end = today
        if period == "day":
            start = today
        elif period == "month":
            start = today - timedelta(days=29)
        else:  # week（含 custom 缺参时的回退）
            start = today - timedelta(days=6)

    stmt = (
        select(ApiUsageLog)
        .where(ApiUsageLog.log_date >= start, ApiUsageLog.log_date <= end)
        .order_by(ApiUsageLog.log_date.desc(), ApiUsageLog.api_type, ApiUsageLog.model)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()

    rows = [
        ApiUsageRow(
            log_date=r.log_date,
            model=r.model,
            api_type=r.api_type,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.prompt_tokens + r.completion_tokens,
            request_count=r.request_count,
        )
        for r in logs
    ]

    # 按 model + api_type 汇总
    summary_map: dict[tuple[str, str], ModelSummary] = {}
    for r in rows:
        key = (r.model, r.api_type)
        if key not in summary_map:
            summary_map[key] = ModelSummary(
                model=r.model,
                api_type=r.api_type,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                request_count=0,
            )
        s = summary_map[key]
        s.prompt_tokens += r.prompt_tokens
        s.completion_tokens += r.completion_tokens
        s.total_tokens += r.total_tokens
        s.request_count += r.request_count

    summary = sorted(summary_map.values(), key=lambda x: x.total_tokens, reverse=True)
    grand_total_tokens = sum(s.total_tokens for s in summary)
    grand_total_requests = sum(s.request_count for s in summary)

    return ApiUsageStats(
        period=period,
        start_date=start,
        end_date=end,
        rows=rows,
        summary=summary,
        grand_total_tokens=grand_total_tokens,
        grand_total_requests=grand_total_requests,
    )
