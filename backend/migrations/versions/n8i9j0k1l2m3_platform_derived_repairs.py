"""Persist administrator estimates and bounded platform repair jobs."""
from alembic import op

revision = "n8i9j0k1l2m3"
down_revision = "m7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade():
    from app.models.derived_state_repair import DerivedStateRepair
    DerivedStateRepair.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    from app.models.derived_state_repair import DerivedStateRepair
    DerivedStateRepair.__table__.drop(op.get_bind(), checkfirst=True)
