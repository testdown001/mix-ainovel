"""user_quotas.credit_purchased 永久积分池（加油包充值所得，不随月度重置清零）

Revision ID: c7f8a9b0d1e2
Revises: b1c2d3e4f5a6
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa

revision = "c7f8a9b0d1e2"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_quotas",
        sa.Column("credit_purchased", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_quotas", "credit_purchased")
