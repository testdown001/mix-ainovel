"""Persist resumable outline generation task progress.

Revision ID: g1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-08-24
"""
from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "g1b2c3d4e5f6"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def _inspector() -> Any:
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if _inspector().has_table("outline_generation_tasks"):
        return
    op.create_table(
        "outline_generation_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("start_chapter", sa.Integer(), nullable=False),
        sa.Column("total_chapters", sa.Integer(), nullable=False),
        sa.Column("chapter_numbers", sa.JSON(), nullable=False),
        sa.Column("completed_numbers", sa.JSON(), nullable=False),
        sa.Column("failed_numbers", sa.JSON(), nullable=False),
        sa.Column("current_batch_start", sa.Integer(), nullable=True),
        sa.Column("current_batch_end", sa.Integer(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("estimated_remaining_seconds", sa.Integer(), nullable=True),
        sa.Column("estimated_total_chapters", sa.Integer(), nullable=True),
        sa.Column("user_prompt", sa.Text(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outline_generation_tasks_project_id", "outline_generation_tasks", ["project_id"])
    op.create_index("ix_outline_generation_tasks_user_id", "outline_generation_tasks", ["user_id"])
    op.create_index("ix_outline_generation_tasks_status", "outline_generation_tasks", ["status"])
    op.create_index(
        "ix_outline_generation_tasks_project_status",
        "outline_generation_tasks",
        ["project_id", "status"],
    )


def downgrade() -> None:
    if _inspector().has_table("outline_generation_tasks"):
        op.drop_table("outline_generation_tasks")
