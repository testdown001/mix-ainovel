"""reference_novels.style_guide 写法基准(可执行的写法约束)

Revision ID: f6b7c8d9e0a1
Revises: e5a6b7c8d9f0
Create Date: 2026-08-14

存在性守卫（规约见 CLAUDE.md）：启动修复 init_db._ensure_columns 永远先于迁移执行，
不守卫的 ADD COLUMN 在已管理的库上必撞 Duplicate column。
"""
from alembic import op
import sqlalchemy as sa

revision = "f6b7c8d9e0a1"
down_revision = "e5a6b7c8d9f0"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("reference_novels", "style_guide"):
        op.add_column(
            "reference_novels",
            sa.Column("style_guide", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("reference_novels", "style_guide"):
        op.drop_column("reference_novels", "style_guide")
