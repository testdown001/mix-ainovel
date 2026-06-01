from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..db.base import Base


class Plan(Base):
    """会员套餐表。"""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    period: Mapped[str] = mapped_column(String(32), default="monthly", nullable=False)
    daily_chapter_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_novels: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 订阅档位（free / creator / flagship）——驱动特性门控与定价页能力展示
    tier: Mapped[str] = mapped_column(String(32), default="free", nullable=False, server_default="free")
    features: Mapped[str | None] = mapped_column(Text)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
