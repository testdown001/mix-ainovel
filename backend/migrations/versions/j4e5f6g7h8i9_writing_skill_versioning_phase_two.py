"""Add versioned writing skill cards, immutable versions and usage receipts.

Revision ID: j4e5f6g7h8i9
Revises: i3d4e5f6g7h8
Create Date: 2026-08-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "j4e5f6g7h8i9"
down_revision = "i3d4e5f6g7h8"
branch_labels = None
depends_on = None

BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if not inspector.has_table("writing_skills"):
        op.create_table(
            "writing_skills",
            sa.Column("id", BIGINT, autoincrement=True, nullable=False),
            sa.Column("skill_key", sa.String(100), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("category", sa.String(64), nullable=False, server_default="style"),
            sa.Column("icon", sa.String(16), nullable=False, server_default="✨"),
            sa.Column("scope", sa.String(16), nullable=False, server_default="system"),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("project_id", sa.String(36), nullable=True),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("execution_mode", sa.String(16), nullable=False, server_default="policy"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("skill_key", name="uq_writing_skills_skill_key"),
        )
        op.create_index("ix_writing_skills_skill_key", "writing_skills", ["skill_key"])
        op.create_index("ix_writing_skills_owner_user_id", "writing_skills", ["owner_user_id"])
        op.create_index("ix_writing_skills_project_id", "writing_skills", ["project_id"])
        op.create_index("ix_writing_skills_scope_project", "writing_skills", ["scope", "project_id"])

    inspector = _inspector()
    if not inspector.has_table("writing_skill_versions"):
        op.create_table(
            "writing_skill_versions",
            sa.Column("id", BIGINT, autoincrement=True, nullable=False),
            sa.Column("skill_id", BIGINT, nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("version_label", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("phase", sa.String(32), nullable=False, server_default="pre_prompt"),
            sa.Column("rules", sa.JSON(), nullable=False),
            sa.Column("prohibitions", sa.JSON(), nullable=False),
            sa.Column("checker_keys", sa.JSON(), nullable=False),
            sa.Column("retrieval_hints", sa.JSON(), nullable=False),
            sa.Column("prompt_hints", sa.JSON(), nullable=False),
            sa.Column("verify_hints", sa.JSON(), nullable=False),
            sa.Column("change_note", sa.String(500), nullable=True),
            sa.Column("source", sa.String(32), nullable=False, server_default="author"),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("published_by_user_id", sa.Integer(), nullable=True),
            sa.Column("parent_version_id", BIGINT, nullable=True),
            sa.Column("checksum", sa.String(64), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["skill_id"], ["writing_skills.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["parent_version_id"], ["writing_skill_versions.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("skill_id", "version_number", name="uq_writing_skill_versions_number"),
        )
        for name, cols in (
            ("ix_writing_skill_versions_skill_id", ["skill_id"]),
            ("ix_writing_skill_versions_status", ["status"]),
            ("ix_writing_skill_versions_skill_status", ["skill_id", "status"]),
            ("ix_writing_skill_versions_created_by_user_id", ["created_by_user_id"]),
            ("ix_writing_skill_versions_published_by_user_id", ["published_by_user_id"]),
            ("ix_writing_skill_versions_parent_version_id", ["parent_version_id"]),
            ("ix_writing_skill_versions_checksum", ["checksum"]),
        ):
            op.create_index(name, "writing_skill_versions", cols)

    inspector = _inspector()
    if not inspector.has_table("writing_skill_usages"):
        op.create_table(
            "writing_skill_usages",
            sa.Column("id", BIGINT, autoincrement=True, nullable=False),
            sa.Column("skill_id", BIGINT, nullable=True),
            sa.Column("skill_version_id", BIGINT, nullable=True),
            sa.Column("skill_key", sa.String(100), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("project_id", sa.String(36), nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(32), nullable=False, server_default="generation"),
            sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("changed", sa.Boolean(), nullable=True),
            sa.Column("accepted", sa.Boolean(), nullable=True),
            sa.Column("before_score", sa.Float(), nullable=True),
            sa.Column("after_score", sa.Float(), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["skill_id"], ["writing_skills.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["skill_version_id"], ["writing_skill_versions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        for name, cols in (
            ("ix_writing_skill_usages_skill_id", ["skill_id"]),
            ("ix_writing_skill_usages_skill_version_id", ["skill_version_id"]),
            ("ix_writing_skill_usages_skill_key", ["skill_key"]),
            ("ix_writing_skill_usages_user_id", ["user_id"]),
            ("ix_writing_skill_usages_project_id", ["project_id"]),
            ("ix_writing_skill_usages_created_at", ["created_at"]),
            ("ix_writing_skill_usages_project_created", ["project_id", "created_at"]),
            ("ix_writing_skill_usages_skill_version", ["skill_id", "skill_version_id"]),
        ):
            op.create_index(name, "writing_skill_usages", cols)


def downgrade() -> None:
    inspector = _inspector()
    for table in ("writing_skill_usages", "writing_skill_versions", "writing_skills"):
        if inspector.has_table(table):
            op.drop_table(table)
