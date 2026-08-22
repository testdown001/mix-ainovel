"""M2：章节可靠保存的版本基线。

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-21
"""
from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def _inspector() -> Any:
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    return _inspector().has_table(table) and column in {
        item["name"] for item in _inspector().get_columns(table)
    }


def upgrade() -> None:
    if not _has_column("chapters", "revision_id"):
        op.add_column(
            "chapters",
            sa.Column("revision_id", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column("chapters", "content_hash"):
        op.add_column("chapters", sa.Column("content_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chapters") as batch_op:
        if _has_column("chapters", "content_hash"):
            batch_op.drop_column("content_hash")
        if _has_column("chapters", "revision_id"):
            batch_op.drop_column("revision_id")
