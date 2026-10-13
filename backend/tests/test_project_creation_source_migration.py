"""Existing novels stay protected, including when startup already added the column."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_provenance_migration_is_idempotent_and_protects_existing_rows():
    path = Path(__file__).resolve().parents[1] / "migrations/versions/l6g7h8i9j0k1_project_creation_source.py"
    spec = importlib.util.spec_from_file_location("source_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE novel_projects (id VARCHAR(36) PRIMARY KEY, title TEXT)"))
        conn.execute(text("INSERT INTO novel_projects (id, title) VALUES ('old', '已有 AI 小说')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.upgrade()
        assert conn.scalar(text("SELECT creation_source FROM novel_projects WHERE id='old'")) == "user"
        column = next(c for c in inspect(conn).get_columns("novel_projects") if c["name"] == "creation_source")
        assert column["nullable"] is False
    engine.dispose()
