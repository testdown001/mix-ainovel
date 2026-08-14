"""reference_novels.beat_library 参考小说桥段库(情境→手法的可检索条目)

Revision ID: e5a6b7c8d9f0
Revises: d8e9f0a1b2c3
Create Date: 2026-08-14

必须做存在性守卫：应用启动的 init_db._ensure_columns 也会补这一列，而部署顺序永远是
「先起新容器（启动修复跑掉）、后跑迁移」——不守卫的 ADD COLUMN 在已管理的库上必然
撞出 Duplicate column（本迁移首次上线时就撞了）。守卫后迁移的职责退化为把
alembic_version 推进到位。
"""
from alembic import op
import sqlalchemy as sa

revision = "e5a6b7c8d9f0"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("reference_novels", "beat_library"):
        op.add_column(
            "reference_novels",
            sa.Column("beat_library", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("reference_novels", "beat_library"):
        op.drop_column("reference_novels", "beat_library")
