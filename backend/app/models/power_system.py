# AIMETA P=力量体系模型_支持等级与境界约束|R=力量体系_等级阶段|NR=不含业务逻辑|E=PowerSystem_PowerLevel|X=internal|A=ORM模型|D=sqlalchemy|S=none|RD=./README.ai
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

BIGINT_PK_TYPE = BigInteger().with_variant(Integer, "sqlite")  # SQLite 需 INTEGER 才能自增

class PowerSystem(Base):
    """
    力量/职业体系模型。
    用于定义小说的修仙境界、魔法等级、职业等特定能力约束系统。
    """
    __tablename__ = "power_systems"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="体系名称，如 '修仙境界'、'魔法师等级'")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="体系描述与核心规则")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    levels: Mapped[list["PowerLevel"]] = relationship(
        "PowerLevel", back_populates="system", cascade="all, delete-orphan", order_by="PowerLevel.level_order"
    )

class PowerLevel(Base):
    """
    力量/职业体系的具体等级或境界阶段。
    """
    __tablename__ = "power_levels"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    system_id: Mapped[int] = mapped_column(
        ForeignKey("power_systems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="排序，表示等级高低，数字越大等级越高")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="阶段名称，如 '筑基期'、'大魔导师'")
    abilities: Mapped[Optional[str]] = mapped_column(Text, comment="此阶段角色具有的能力表现")
    limitations: Mapped[Optional[str]] = mapped_column(Text, comment="此阶段角色的弱点或能力限制")
    breakthrough_conditions: Mapped[Optional[str]] = mapped_column(Text, comment="突破到下一等级的要求")

    system: Mapped["PowerSystem"] = relationship("PowerSystem", back_populates="levels")
