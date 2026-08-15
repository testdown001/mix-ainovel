"""灵感模式质量机制：novel_projects.concept_dossier/exclusions + novel_blueprints.review_report

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-15

存在性守卫（规约见 CLAUDE.md）：启动修复 init_db._ensure_columns 永远先于迁移执行，
不守卫的 ADD COLUMN 在已管理的库上必撞 Duplicate column。
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("novel_projects", "concept_dossier"):
        op.add_column("novel_projects", sa.Column("concept_dossier", sa.JSON(), nullable=True))
    if not _has_column("novel_projects", "exclusions"):
        op.add_column("novel_projects", sa.Column("exclusions", sa.Text(), nullable=True))
    if not _has_column("novel_blueprints", "review_report"):
        op.add_column("novel_blueprints", sa.Column("review_report", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_column("novel_blueprints", "review_report"):
        op.drop_column("novel_blueprints", "review_report")
    if _has_column("novel_projects", "exclusions"):
        op.drop_column("novel_projects", "exclusions")
    if _has_column("novel_projects", "concept_dossier"):
        op.drop_column("novel_projects", "concept_dossier")
