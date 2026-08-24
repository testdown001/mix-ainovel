# AIMETA P=章纲后台生成任务模型|R=持久化批量章纲进度与恢复状态|NR=不含生成逻辑|E=OutlineGenerationTask|X=internal|A=ORM|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class OutlineGenerationTask(Base):
    """可跨页面、跨应用副本查询的批量章纲生成任务。"""

    __tablename__ = "outline_generation_tasks"
    __table_args__ = (
        Index("ix_outline_generation_tasks_project_status", "project_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="任务已进入队列")

    start_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chapters: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False)
    completed_numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False, default=list)
    failed_numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False, default=list)
    generate_chapters: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chapter_generation_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    body_completed_numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False, default=list)
    body_failed_numbers: Mapped[List[int]] = mapped_column(JSON, nullable=False, default=list)
    current_body_chapter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    current_batch_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_batch_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_remaining_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    estimated_total_chapters: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
