"""Additive schema upgrades preserve legacy manuscript data on SQLite."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.models.chapter_derivation import ChapterDerivationJob
from app.models.derived_state_repair import DerivedStateRepair


def migration(name):
    path = Path(__file__).parents[1] / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_upgrade_is_additive_repeatable_and_preserves_rows():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        for sql in (
            "CREATE TABLE users (id INTEGER PRIMARY KEY)",
            "CREATE TABLE novel_projects (id VARCHAR(36) PRIMARY KEY)",
            "CREATE TABLE chapters (id INTEGER PRIMARY KEY, legacy_text TEXT)",
            "CREATE TABLE foreshadowings (id INTEGER PRIMARY KEY)",
            "CREATE TABLE foreshadowing_resolutions (id INTEGER PRIMARY KEY)",
        ):
            conn.execute(text(sql))
        conn.execute(text("INSERT INTO chapters VALUES (1, '作者的既有正文')"))
        operations = Operations(MigrationContext.configure(conn))
        core = migration("m7h8i9j0k1l2_canonical_derivations.py")
        repair = migration("n8i9j0k1l2m3_platform_derived_repairs.py")
        core.op = repair.op = operations
        core.upgrade()
        repair.upgrade()
        core.upgrade()
        repair.upgrade()
        assert conn.execute(text("SELECT legacy_text FROM chapters WHERE id=1")).scalar_one() == "作者的既有正文"
        columns = {c["name"] for c in inspect(conn).get_columns("chapters")}
        assert "active_index_revision_id" in columns
        assert inspect(conn).has_table("chapter_derivation_jobs")
        assert inspect(conn).has_table("derived_state_repairs")
        repair.downgrade()
        core.downgrade()
        assert conn.execute(text("SELECT legacy_text FROM chapters WHERE id=1")).scalar_one() == "作者的既有正文"
    engine.dispose()


def test_new_tables_compile_for_mysql_without_sqlite_only_types():
    for model in (ChapterDerivationJob, DerivedStateRepair):
        ddl = str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        assert "JSON" in ddl and "FOREIGN KEY" in ddl
