"""M3：章节不可变修订链的来源与父版本字段。

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-08-21
"""
from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def _inspector() -> Any:
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    return _inspector().has_table(table) and column in {
        item["name"] for item in _inspector().get_columns(table)
    }


def _has_index(table: str, index: str) -> bool:
    return _inspector().has_table(table) and index in {
        item["name"] for item in _inspector().get_indexes(table)
    }


def upgrade() -> None:
    # Nullable keeps the migration safe for existing generated/manual snapshots. New rows
    # always set these values in ChapterRevisionService; old rows remain explicitly legacy.
    if not _has_column("chapter_versions", "parent_version_id"):
        op.add_column("chapter_versions", sa.Column("parent_version_id", sa.BigInteger(), nullable=True))
    if not _has_column("chapter_versions", "source"):
        op.add_column(
            "chapter_versions",
            sa.Column("source", sa.String(length=32), nullable=False, server_default="legacy"),
        )
    if not _has_column("chapter_versions", "content_hash"):
        op.add_column("chapter_versions", sa.Column("content_hash", sa.String(length=64), nullable=True))
    if not _has_column("chapter_versions", "change_note"):
        op.add_column("chapter_versions", sa.Column("change_note", sa.String(length=500), nullable=True))
    if not _has_column("chapter_versions", "created_by_user_id"):
        op.add_column("chapter_versions", sa.Column("created_by_user_id", sa.BigInteger(), nullable=True))

    # Foreign-key DDL is intentionally omitted for self/user references: production has
    # historical MySQL deployments and SQLite test environments with divergent ALTER
    # capabilities. The ORM model declares referential intent; project ownership checks
    # prevent cross-project access at the API boundary.
    for index, columns in (
        ("ix_chapter_versions_parent_version_id", ["parent_version_id"]),
        ("ix_chapter_versions_source", ["source"]),
        ("ix_chapter_versions_content_hash", ["content_hash"]),
        ("ix_chapter_versions_created_by_user_id", ["created_by_user_id"]),
    ):
        if not _has_index("chapter_versions", index):
            op.create_index(index, "chapter_versions", columns, unique=False)


def downgrade() -> None:
    with op.batch_alter_table("chapter_versions") as batch_op:
        for index in (
            "ix_chapter_versions_created_by_user_id",
            "ix_chapter_versions_content_hash",
            "ix_chapter_versions_source",
            "ix_chapter_versions_parent_version_id",
        ):
            if _has_index("chapter_versions", index):
                batch_op.drop_index(index)
        for column in (
            "created_by_user_id",
            "change_note",
            "content_hash",
            "source",
            "parent_version_id",
        ):
            if _has_column("chapter_versions", column):
                batch_op.drop_column(column)
