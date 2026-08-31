"""Add project-scoped writing skill copies for phase three."""

from alembic import op
import sqlalchemy as sa


revision = "k5f6g7h8i9j0"
down_revision = "j4e5f6g7h8i9"
branch_labels = None
depends_on = None

BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot ALTER a table to add a foreign key; batch mode safely
        # rebuilds the small metadata table while preserving its rows.
        with op.batch_alter_table("writing_skills", recreate="always") as batch:
            batch.add_column(sa.Column("base_skill_id", BIGINT, nullable=True))
            batch.add_column(sa.Column("base_version_id", BIGINT, nullable=True))
            batch.create_foreign_key("fk_writing_skills_base_skill_id", "writing_skills", ["base_skill_id"], ["id"], ondelete="SET NULL")
            batch.create_foreign_key("fk_writing_skills_base_version_id", "writing_skill_versions", ["base_version_id"], ["id"], ondelete="SET NULL")
    else:
        op.add_column("writing_skills", sa.Column("base_skill_id", BIGINT, nullable=True))
        op.add_column("writing_skills", sa.Column("base_version_id", BIGINT, nullable=True))
        op.create_foreign_key("fk_writing_skills_base_skill_id", "writing_skills", "writing_skills", ["base_skill_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_writing_skills_base_version_id", "writing_skills", "writing_skill_versions", ["base_version_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_writing_skills_base_skill_id", "writing_skills", ["base_skill_id"])
    op.create_index("ix_writing_skills_base_version_id", "writing_skills", ["base_version_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_writing_skills_base_version_id", table_name="writing_skills")
        op.drop_index("ix_writing_skills_base_skill_id", table_name="writing_skills")
        with op.batch_alter_table("writing_skills", recreate="always") as batch:
            batch.drop_constraint("fk_writing_skills_base_version_id", type_="foreignkey")
            batch.drop_constraint("fk_writing_skills_base_skill_id", type_="foreignkey")
            batch.drop_column("base_version_id")
            batch.drop_column("base_skill_id")
    else:
        op.drop_constraint("fk_writing_skills_base_version_id", "writing_skills", type_="foreignkey")
        op.drop_constraint("fk_writing_skills_base_skill_id", "writing_skills", type_="foreignkey")
        op.drop_index("ix_writing_skills_base_version_id", table_name="writing_skills")
        op.drop_index("ix_writing_skills_base_skill_id", table_name="writing_skills")
        op.drop_column("writing_skills", "base_version_id")
        op.drop_column("writing_skills", "base_skill_id")
