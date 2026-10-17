"""Version-bound derivation outbox and acknowledged chapter index publication."""
from alembic import op
import sqlalchemy as sa

revision = "m7h8i9j0k1l2"
down_revision = "l6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    additions = {
        "chapters": [sa.Column("active_index_revision_id", sa.String(64), nullable=True)],
        "foreshadowings": [
            sa.Column("source_derivation_id", sa.String(36), nullable=True),
            sa.Column("origin", sa.String(16), nullable=False, server_default="legacy"),
        ],
        "foreshadowing_resolutions": [sa.Column("source_derivation_id", sa.String(36), nullable=True)],
    }
    for table, columns in additions.items():
        if not inspector.has_table(table):
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)
    # Importing the registered ORM graph resolves project/chapter foreign keys.
    from app.models.chapter_derivation import ChapterDerivationJob
    ChapterDerivationJob.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    from app.models.chapter_derivation import ChapterDerivationJob
    ChapterDerivationJob.__table__.drop(bind, checkfirst=True)
    for table, names in {
        "foreshadowing_resolutions": ["source_derivation_id"],
        "foreshadowings": ["source_derivation_id", "origin"],
        "chapters": ["active_index_revision_id"],
    }.items():
        inspector = sa.inspect(bind)
        if not inspector.has_table(table):
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name in names:
            if name in existing:
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(name)
