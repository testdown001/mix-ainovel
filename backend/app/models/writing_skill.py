# AIMETA P=写作技能版本模型_技能卡_版本_使用回执|R=版本化技能治理|NR=不含业务逻辑|E=WritingSkill_WritingSkillVersion_WritingSkillUsage|X=internal|A=ORM模型|D=sqlalchemy|S=none|RD=./README.ai
"""Versioned writing skill models.

Skill definitions are deliberately declarative. The database stores prompts,
rules and checker keys, never executable Python or shell code.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base
from .novel import BIGINT_PK_TYPE


class WritingSkill(Base):
    """Stable skill card visible to authors and administrators."""

    __tablename__ = "writing_skills"
    __table_args__ = (
        UniqueConstraint("skill_key", name="uq_writing_skills_skill_key"),
        Index("ix_writing_skills_scope_project", "scope", "project_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    skill_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="style")
    icon: Mapped[str] = mapped_column(String(16), nullable=False, default="✨")
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="system", server_default="system")
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=True, index=True)
    # 项目级技能副本的来源。保留来源版本可在作者编辑时展示可解释的差异。
    base_skill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_skills.id", ondelete="SET NULL"), nullable=True, index=True)
    base_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_skill_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="policy", server_default="policy")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WritingSkillVersion(Base):
    """Immutable skill policy snapshot.

    Publishing retires the previous version and never edits an already
    published policy. Rollback is implemented by cloning an old version.
    """

    __tablename__ = "writing_skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version_number", name="uq_writing_skill_versions_number"),
        Index("ix_writing_skill_versions_skill_status", "skill_id", "status"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("writing_skills.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft", index=True)
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="pre_prompt", server_default="pre_prompt")
    rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    prohibitions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    checker_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    retrieval_hints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    prompt_hints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    verify_hints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    change_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="author", server_default="author")
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    published_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_skill_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WritingSkillUsage(Base):
    """Per-application receipt used to calculate skill effectiveness."""

    __tablename__ = "writing_skill_usages"
    __table_args__ = (
        Index("ix_writing_skill_usages_project_created", "project_id", "created_at"),
        Index("ix_writing_skill_usages_skill_version", "skill_id", "skill_version_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    skill_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_skills.id", ondelete="SET NULL"), nullable=True, index=True)
    skill_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("writing_skill_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    skill_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("novel_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="generation", server_default="generation")
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    changed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    accepted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    before_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    after_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
