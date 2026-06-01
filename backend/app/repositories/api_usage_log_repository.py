import logging
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from ..models.api_usage_log import ApiUsageLog


class ApiUsageLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: ApiUsageLog) -> ApiUsageLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def cleanup_old_records(self, days: int = 30) -> int:
        """删除超过指定天数的旧记录，返回删除行数。"""
        cutoff = date.today() - timedelta(days=days)
        stmt = delete(ApiUsageLog).where(ApiUsageLog.log_date < cutoff)
        result = await self.session.execute(stmt)
        await self.session.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info("已清理 %d 条超过 %d 天的 API 用量记录", deleted, days)
        return deleted

    async def get_stats(
        self,
        start_date: date,
        end_date: date,
    ) -> dict:
        """聚合指定日期范围内的总 Token、总请求次数、模型种类数。"""
        stmt = (
            select(
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("total_tokens"),
                func.count().label("total_requests"),
                func.count(func.distinct(ApiUsageLog.model_name)).label("model_count"),
            )
            .where(ApiUsageLog.log_date >= start_date)
            .where(ApiUsageLog.log_date <= end_date)
        )
        row = (await self.session.execute(stmt)).one()
        return {
            "total_tokens": int(row.total_tokens),
            "total_requests": int(row.total_requests),
            "model_count": int(row.model_count),
        }

    async def get_model_summary(
        self,
        start_date: date,
        end_date: date,
    ) -> List[dict]:
        """按模型 + 调用类型分组统计 Token 和请求次数。"""
        stmt = (
            select(
                ApiUsageLog.model_name,
                ApiUsageLog.call_type,
                func.sum(ApiUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(ApiUsageLog.completion_tokens).label("completion_tokens"),
                func.sum(ApiUsageLog.total_tokens).label("total_tokens"),
                func.count().label("request_count"),
                func.sum(ApiUsageLog.cost).label("total_cost"),
            )
            .where(ApiUsageLog.log_date >= start_date)
            .where(ApiUsageLog.log_date <= end_date)
            .group_by(ApiUsageLog.model_name, ApiUsageLog.call_type)
            .order_by(func.sum(ApiUsageLog.total_tokens).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "model_name": r.model_name,
                "call_type": r.call_type or "chat",
                "prompt_tokens": int(r.prompt_tokens or 0),
                "completion_tokens": int(r.completion_tokens or 0),
                "total_tokens": int(r.total_tokens or 0),
                "request_count": int(r.request_count),
                "total_cost": float(r.total_cost or 0),
            }
            for r in rows
        ]

    async def get_daily_details(
        self,
        start_date: date,
        end_date: date,
    ) -> List[dict]:
        """按日期分组统计每日用量。"""
        stmt = (
            select(
                ApiUsageLog.log_date,
                func.sum(ApiUsageLog.total_tokens).label("total_tokens"),
                func.sum(ApiUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(ApiUsageLog.completion_tokens).label("completion_tokens"),
                func.count().label("request_count"),
                func.count(func.distinct(ApiUsageLog.model_name)).label("model_count"),
                func.sum(ApiUsageLog.cost).label("total_cost"),
            )
            .where(ApiUsageLog.log_date >= start_date)
            .where(ApiUsageLog.log_date <= end_date)
            .group_by(ApiUsageLog.log_date)
            .order_by(ApiUsageLog.log_date.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "date": r.log_date.isoformat(),
                "total_tokens": int(r.total_tokens or 0),
                "prompt_tokens": int(r.prompt_tokens or 0),
                "completion_tokens": int(r.completion_tokens or 0),
                "request_count": int(r.request_count),
                "model_count": int(r.model_count),
                "total_cost": float(r.total_cost or 0),
            }
            for r in rows
        ]
