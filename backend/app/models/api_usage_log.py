# AIMETA P=API用量日志模型_按天按模型记录token消耗|R=api_usage_logs表|E=ApiUsageLog|X=internal|A=ORM模型|D=sqlalchemy|S=none
from datetime import date

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ApiUsageLog(Base):
    """每天按 model + api_type 汇总的 token 用量，用于管理后台用量统计。"""

    __tablename__ = "api_usage_logs"
    __table_args__ = (
        UniqueConstraint("log_date", "model", "api_type", name="uq_api_usage_log"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_type: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
