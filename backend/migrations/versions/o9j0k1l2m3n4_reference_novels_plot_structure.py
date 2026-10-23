"""reference_novels.plot_structure 剧情结构（阶段/卷、转折点、升级轴）

Revision ID: o9j0k1l2m3n4
Revises: n8i9j0k1l2m3
Create Date: 2026-10-23

存在性守卫（规约见 CLAUDE.md）：启动修复 init_db._ensure_columns 永远先于迁移执行，
不守卫的 ADD COLUMN 在已管理的库上必撞 Duplicate column。
"""
from alembic import op
import sqlalchemy as sa

revision = "o9j0k1l2m3n4"
down_revision = "n8i9j0k1l2m3"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("reference_novels", "plot_structure"):
        op.add_column("reference_novels", sa.Column("plot_structure", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_column("reference_novels", "plot_structure"):
        op.drop_column("reference_novels", "plot_structure")
