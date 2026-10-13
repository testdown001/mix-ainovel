"""Add trusted project provenance; protect all existing projects by default."""

from alembic import op
import sqlalchemy as sa

revision = "l6g7h8i9j0k1"
down_revision = "k5f6g7h8i9j0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("novel_projects")}
    if "creation_source" not in columns:
        op.add_column("novel_projects", sa.Column(
            "creation_source", sa.String(32), nullable=False, server_default="user",
        ))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("novel_projects")}
    if "creation_source" in columns:
        op.drop_column("novel_projects", "creation_source")
