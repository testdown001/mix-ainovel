"""novel_projects / chapter_versions.ai_assisted 创作标识

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-08-15

存在性守卫（规约见 CLAUDE.md）：启动修复 init_db._ensure_columns 永远先于迁移执行，
不守卫的 ADD COLUMN 在已管理的库上必撞 Duplicate column。
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a5b6"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("novel_projects", "ai_assisted"):
        op.add_column(
            "novel_projects",
            sa.Column(
                "ai_assisted",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
        )
    if not _has_column("chapter_versions", "ai_assisted"):
        op.add_column(
            "chapter_versions",
            sa.Column(
                "ai_assisted",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    if _has_column("chapter_versions", "ai_assisted"):
        op.drop_column("chapter_versions", "ai_assisted")
    if _has_column("novel_projects", "ai_assisted"):
        op.drop_column("novel_projects", "ai_assisted")
