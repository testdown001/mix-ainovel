"""Add optional chapter-body phase to outline generation tasks.

Revision ID: h2c3d4e5f6g7
Revises: g1b2c3d4e5f6
Create Date: 2026-08-24
"""
from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "h2c3d4e5f6g7"
down_revision = "g1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _inspector() -> Any:
    return sa.inspect(op.get_bind())


def _columns() -> set[str]:
    return {column["name"] for column in _inspector().get_columns("outline_generation_tasks")}


def upgrade() -> None:
    if not _inspector().has_table("outline_generation_tasks"):
        return

    columns = _columns()
    with op.batch_alter_table("outline_generation_tasks") as batch:
        if "generate_chapters" not in columns:
            batch.add_column(
                sa.Column(
                    "generate_chapters",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if "chapter_generation_config" not in columns:
            batch.add_column(sa.Column("chapter_generation_config", sa.JSON(), nullable=True))
        if "body_completed_numbers" not in columns:
            batch.add_column(sa.Column("body_completed_numbers", sa.JSON(), nullable=True))
        if "body_failed_numbers" not in columns:
            batch.add_column(sa.Column("body_failed_numbers", sa.JSON(), nullable=True))
        if "current_body_chapter" not in columns:
            batch.add_column(sa.Column("current_body_chapter", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE outline_generation_tasks "
            "SET body_completed_numbers = '[]' WHERE body_completed_numbers IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE outline_generation_tasks "
            "SET body_failed_numbers = '[]' WHERE body_failed_numbers IS NULL"
        )
    )
    with op.batch_alter_table("outline_generation_tasks") as batch:
        batch.alter_column(
            "body_completed_numbers",
            existing_type=sa.JSON(),
            nullable=False,
        )
        batch.alter_column(
            "body_failed_numbers",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    if not _inspector().has_table("outline_generation_tasks"):
        return
    columns = _columns()
    with op.batch_alter_table("outline_generation_tasks") as batch:
        for name in (
            "current_body_chapter",
            "body_failed_numbers",
            "body_completed_numbers",
            "chapter_generation_config",
            "generate_chapters",
        ):
            if name in columns:
                batch.drop_column(name)
