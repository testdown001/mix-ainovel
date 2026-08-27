"""Add scoped creative memory learning loop and generation receipts.

Revision ID: i3d4e5f6g7h8
Revises: h2c3d4e5f6g7
Create Date: 2026-08-27
"""
from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "i3d4e5f6g7h8"
down_revision = "h2c3d4e5f6g7"
branch_labels = None
depends_on = None


def _inspector() -> Any:
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if not inspector.has_table("creative_memory_items"):
        op.create_table(
            "creative_memory_items",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=True),
            sa.Column("source_project_id", sa.String(length=36), nullable=True),
            sa.Column("scope", sa.String(length=16), server_default="novel", nullable=False),
            sa.Column("volume_number", sa.Integer(), nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("category", sa.String(length=32), server_default="style", nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=16), server_default="candidate", nullable=False),
            sa.Column("confidence", sa.Float(), server_default="0.7", nullable=False),
            sa.Column("pinned", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("source_type", sa.String(length=32), server_default="manual", nullable=False),
            sa.Column("source_version_id", sa.BigInteger(), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("dedupe_key", sa.String(length=64), nullable=False),
            sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_project_id"], ["novel_projects.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["source_version_id"], ["chapter_versions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dedupe_key", name="uq_creative_memory_dedupe_key"),
        )
        op.create_index("ix_creative_memory_items_user_id", "creative_memory_items", ["user_id"])
        op.create_index("ix_creative_memory_items_project_id", "creative_memory_items", ["project_id"])
        op.create_index("ix_creative_memory_items_source_project_id", "creative_memory_items", ["source_project_id"])
        op.create_index("ix_creative_memory_items_status", "creative_memory_items", ["status"])
        op.create_index("ix_creative_memory_items_source_version_id", "creative_memory_items", ["source_version_id"])
        op.create_index("ix_creative_memory_user_status", "creative_memory_items", ["user_id", "status"])
        op.create_index("ix_creative_memory_project_scope", "creative_memory_items", ["project_id", "scope"])
        op.create_index("ix_creative_memory_source_project", "creative_memory_items", ["source_project_id", "status"])

    if not inspector.has_table("creative_memory_learning_events"):
        op.create_table(
            "creative_memory_learning_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("event_key", sa.String(length=160), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("source_type", sa.String(length=32), nullable=False),
            sa.Column("source_version_id", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(length=16), server_default="processing", nullable=False),
            sa.Column("candidate_ids", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_version_id"], ["chapter_versions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key", name="uq_creative_memory_learning_event_key"),
        )
        op.create_index("ix_creative_memory_learning_events_user_id", "creative_memory_learning_events", ["user_id"])
        op.create_index("ix_creative_memory_learning_events_project_id", "creative_memory_learning_events", ["project_id"])
        op.create_index("ix_creative_memory_event_project_chapter", "creative_memory_learning_events", ["project_id", "chapter_number"])

    if not inspector.has_table("creative_memory_receipts"):
        op.create_table(
            "creative_memory_receipts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("memory_ids", sa.JSON(), nullable=False),
            sa.Column("items", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_creative_memory_receipts_user_id", "creative_memory_receipts", ["user_id"])
        op.create_index("ix_creative_memory_receipts_project_id", "creative_memory_receipts", ["project_id"])
        op.create_index(
            "ix_creative_memory_receipt_project_chapter_created",
            "creative_memory_receipts",
            ["project_id", "chapter_number", "created_at"],
        )


def downgrade() -> None:
    inspector = _inspector()
    for table in (
        "creative_memory_receipts",
        "creative_memory_learning_events",
        "creative_memory_items",
    ):
        if inspector.has_table(table):
            op.drop_table(table)
