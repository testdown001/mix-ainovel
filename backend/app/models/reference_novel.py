# AIMETA P=参考小说模型_持久化参考资料|R=参考小说表|NR=不含业务逻辑|E=ReferenceNovel|X=internal|A=ORM模型|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

LONG_TEXT_TYPE = Text().with_variant(LONGTEXT, "mysql")


class ReferenceNovel(Base):
    """参考小说库，用于存储结构化的创作参考档案。"""

    __tablename__ = "reference_novels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    outline_content: Mapped[Optional[str]] = mapped_column(LONG_TEXT_TYPE)
    style_samples_content: Mapped[Optional[str]] = mapped_column(LONG_TEXT_TYPE)
    memory_card: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    genre: Mapped[Optional[str]] = mapped_column(String(128))
    author: Mapped[Optional[str]] = mapped_column(String(128))
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="reference_novels")

