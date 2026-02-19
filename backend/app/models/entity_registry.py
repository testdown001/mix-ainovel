# AIMETA P=实体注册表模型_反幻觉实体追踪|R=实体注册_别名消歧|NR=不含业务逻辑|E=EntityRegistry_EntityAlias|X=internal|A=ORM模型|D=sqlalchemy|S=none|RD=./README.ai
"""
实体注册表数据模型

为反幻觉系统提供基础数据结构：
- EntityRegistry: 注册所有已确认的实体（角色/地点/组织/物品/能力）
- EntityAlias: 管理实体的多种称呼，支持别名消歧
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

BIGINT_PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class EntityRegistry(Base):
    """
    实体注册表

    记录小说项目中所有已确认的实体，包含置信度评分和来源追踪。
    """
    __tablename__ = "entity_registry"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="character/location/organization/item/ability",
    )
    canonical_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    first_chapter: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(
        String(32), default="auto_detected",
        comment="blueprint/manual/auto_detected",
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    properties: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    aliases: Mapped[list["EntityAlias"]] = relationship(
        "EntityAlias", back_populates="entity", cascade="all, delete-orphan",
    )


class EntityAlias(Base):
    """
    实体别名表

    管理同一实体的多种称呼（昵称/头衔/别名），用于别名消歧。
    """
    __tablename__ = "entity_alias"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entity_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(
        String(32), default="alias",
        comment="alias/nickname/title",
    )
    context: Mapped[Optional[str]] = mapped_column(String(255))

    entity: Mapped["EntityRegistry"] = relationship("EntityRegistry", back_populates="aliases")
