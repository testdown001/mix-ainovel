"""novel_projects.share_token 作品公开分享令牌

Revision ID: a7b8c9d0e1f2
Revises: f6b7c8d9e0a1
Create Date: 2026-08-14

存在性守卫（规约见 CLAUDE.md）：启动修复 init_db._ensure_columns 永远先于迁移执行，
不守卫的 ADD COLUMN 在已管理的库上必撞 Duplicate column。init_db 只补列不建索引
（其 _ensure_index 不支持 UNIQUE），唯一索引由本迁移守卫式补建。
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6b7c8d9e0a1"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_novel_projects_share_token"


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def _has_index(table: str, index: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _has_column("novel_projects", "share_token"):
        op.add_column(
            "novel_projects",
            sa.Column("share_token", sa.String(length=64), nullable=True),
        )
    # 全 NULL 列上建唯一索引安全（MySQL 唯一索引允许多个 NULL）
    if not _has_index("novel_projects", _INDEX_NAME):
        op.create_index(_INDEX_NAME, "novel_projects", ["share_token"], unique=True)


def downgrade() -> None:
    if _has_index("novel_projects", _INDEX_NAME):
        op.drop_index(_INDEX_NAME, table_name="novel_projects")
    if _has_column("novel_projects", "share_token"):
        op.drop_column("novel_projects", "share_token")
