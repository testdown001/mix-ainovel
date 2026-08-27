# AIMETA P=创作记忆模型_候选偏好与生成回执|R=四级作用域_学习事件_使用追溯|NR=不含LLM提取逻辑|E=CreativeMemoryItem_CreativeMemoryLearningEvent_CreativeMemoryReceipt|X=internal|A=ORM模型|D=sqlalchemy|S=db
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base
from .novel import BIGINT_PK_TYPE


class CreativeMemoryItem(Base):
    """作者确认后才会进入生成上下文的创作偏好。

    ``project_id`` 表示生效目标：作者级记忆为 NULL，其余作用域绑定作品。
    ``source_project_id`` 永远保留最初学习来源，确保全局记忆仍可追溯。
    """

    __tablename__ = "creative_memory_items"
    __table_args__ = (
        Index("ix_creative_memory_user_status", "user_id", "status"),
        Index("ix_creative_memory_project_scope", "project_id", "scope"),
        Index("ix_creative_memory_source_project", "source_project_id", "status"),
        UniqueConstraint("dedupe_key", name="uq_creative_memory_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="novel", server_default="novel")
    volume_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="style", server_default="style")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate", server_default="candidate", index=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7, server_default="0.7")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default="manual")
    source_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreativeMemoryLearningEvent(Base):
    """一次可重复学习信号的幂等账本。"""

    __tablename__ = "creative_memory_learning_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_creative_memory_learning_event_key"),
        Index("ix_creative_memory_event_project_chapter", "project_id", "chapter_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing", server_default="processing")
    candidate_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CreativeMemoryReceipt(Base):
    """一次章节生成实际采用的创作记忆快照。"""

    __tablename__ = "creative_memory_receipts"
    __table_args__ = (
        Index(
            "ix_creative_memory_receipt_project_chapter_created",
            "project_id",
            "chapter_number",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
