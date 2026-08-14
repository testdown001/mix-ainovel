"""reference_novels.beat_library 参考小说桥段库(情境→手法的可检索条目)

Revision ID: e5a6b7c8d9f0
Revises: d8e9f0a1b2c3
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "e5a6b7c8d9f0"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reference_novels",
        sa.Column("beat_library", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reference_novels", "beat_library")
