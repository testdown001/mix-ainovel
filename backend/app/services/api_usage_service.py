import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.api_usage_log import ApiUsageLog
from ..repositories.api_usage_log_repository import ApiUsageLogRepository

logger = logging.getLogger(__name__)


class ApiUsageService:
    """API 用量统计服务，提供记录写入和多维度聚合查询。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ApiUsageLogRepository(session)

    async def record(
        self,
        *,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost: float = 0.0,
        user_id: Optional[int] = None,
        call_type: str = "chat",
    ) -> None:
        log = ApiUsageLog(
            model_name=model_name or "unknown",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            user_id=user_id,
            call_type=call_type,
            log_date=date.today(),
        )
        await self.repo.create(log)
        await self.session.commit()
        logger.debug(
            "API usage recorded: model=%s tokens=%d user=%s",
            model_name, total_tokens, user_id,
        )

    @staticmethod
    def _resolve_date_range(period: str) -> tuple[date, date]:
        today = date.today()
        if period == "7d":
            return today - timedelta(days=6), today
        elif period == "30d":
            return today - timedelta(days=29), today
        else:
            return today, today

    async def get_overview(self, period: str = "today") -> dict:
        start, end = self._resolve_date_range(period)
        return await self.repo.get_stats(start, end)

    async def get_model_summary(self, period: str = "today") -> List[dict]:
        start, end = self._resolve_date_range(period)
        return await self.repo.get_model_summary(start, end)

    async def get_daily_details(self, period: str = "today") -> List[dict]:
        start, end = self._resolve_date_range(period)
        return await self.repo.get_daily_details(start, end)

    async def cleanup_old(self, days: int = 30) -> int:
        """清理超过指定天数的旧用量记录。"""
        return await self.repo.cleanup_old_records(days)
