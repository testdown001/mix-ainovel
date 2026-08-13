"""user_quotas.expiry_reminded_for 到期提醒幂等锚(会员到期邮件提醒)

Revision ID: d8e9f0a1b2c3
Revises: c7f8a9b0d1e2
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "d8e9f0a1b2c3"
down_revision = "c7f8a9b0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_quotas",
        sa.Column("expiry_reminded_for", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_quotas", "expiry_reminded_for")
