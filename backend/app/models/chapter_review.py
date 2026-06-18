# AIMETA P=章节审核模型_质量审核|R=审核结果存储|NR=记录章节质量审核结果|ChapterReview|X=internal|A=SQLAlchemy|D=orm|S=none|RD=./README.ai
"""章节审核模型 - 质量审核机制"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

BIGINT_PK_TYPE = BigInteger().with_variant(Integer, "sqlite")  # SQLite 需 INTEGER 才能自增


class ChapterReview(Base):
    """章节审核记录 - 质量审核结果"""

    __tablename__ = "chapter_reviews"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # 审核结果
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)

    # 各维度评分
    scores: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="""{
            "consistency": 85,      # 剧情一致性
            "character_depth": 70,  # 角色立体度
            "pacing": 90,          # 节奏张力
            "foreshadowing": 60,   # 伏笔呼应
            "prose_quality": 75,   # 文笔质量
            "emotion_curve": 80    # 情绪曲线
        }"""
    )

    # 问题列表
    issues: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="""[
            {
                "type": "foreshadowing",
                "severity": "high",  # low/medium/high
                "description": "缺少与第3章伏笔的呼应",
                "suggestion": "建议在本章结尾添加..."
            }
        ]"""
    )

    # 审核意见
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 是否需要重写
    rewrite_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 关联章节版本
    chapter_version_id: Mapped[Optional[int]] = mapped_column(
        BIGINT_PK_TYPE, ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 阈值配置（用于判定）
    REVISION_THRESHOLDS = {
        "overall_score": 70,        # 综合评分 >= 70
        "min_dimension_score": 50,  # 单项最低 >= 50
        "max_high_issues": 2,       # 严重问题 <= 2
    }
