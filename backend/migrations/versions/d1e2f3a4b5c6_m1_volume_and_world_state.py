"""M1：分卷一等实体、章节稳定排序与世界状态切片。

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-08-21

既有 ``novel_blueprints.volumes`` 保留不动：本迁移把其内容一次性复制到
``volumes``，后续服务层负责维护双向兼容投影。这样不会阻断已经在线的卷级复盘和
生成提示链路。
"""
from __future__ import annotations

import json
from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _inspector() -> Any:
    return sa.inspect(op.get_bind())


def _has_table(table: str) -> bool:
    return _inspector().has_table(table)


def _has_column(table: str, column: str) -> bool:
    return _has_table(table) and column in {item["name"] for item in _inspector().get_columns(table)}


def _has_index(table: str, index: str) -> bool:
    return _has_table(table) and index in {item["name"] for item in _inspector().get_indexes(table)}


def _json_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result


def _create_tables() -> None:
    if not _has_table("volumes"):
        op.create_table(
            "volumes",
            sa.Column("id", _PK, primary_key=True, autoincrement=True, nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("start_chapter", sa.Integer(), nullable=False),
            sa.Column("end_chapter", sa.Integer(), nullable=False),
            sa.Column("arc_goal", sa.Text(), nullable=True),
            sa.Column("climax_hint", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
            sa.Column("retrospective", sa.JSON(), nullable=True),
            sa.Column("replan", sa.JSON(), nullable=True),
            sa.Column("extra", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("project_id", "position", name="uq_volumes_project_position"),
        )
    if not _has_index("volumes", "ix_volumes_project_id"):
        op.create_index("ix_volumes_project_id", "volumes", ["project_id"], unique=False)
    if not _has_index("volumes", "ix_volumes_project_range"):
        op.create_index("ix_volumes_project_range", "volumes", ["project_id", "start_chapter", "end_chapter"], unique=False)

    if not _has_table("chapter_world_states"):
        op.create_table(
            "chapter_world_states",
            sa.Column("id", _PK, primary_key=True, autoincrement=True, nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("chapter_id", _PK, nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("source_version_id", _PK, nullable=True),
            sa.Column("parent_snapshot_id", _PK, nullable=True),
            sa.Column("origin", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("state", sa.JSON(), nullable=False),
            sa.Column("source_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_version_id"], ["chapter_versions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["parent_snapshot_id"], ["chapter_world_states.id"], ondelete="SET NULL"),
        )
    if not _has_index("chapter_world_states", "ix_chapter_world_states_project_id"):
        op.create_index("ix_chapter_world_states_project_id", "chapter_world_states", ["project_id"], unique=False)
    if not _has_index("chapter_world_states", "ix_chapter_world_states_chapter_id"):
        op.create_index("ix_chapter_world_states_chapter_id", "chapter_world_states", ["chapter_id"], unique=False)
    if not _has_index("chapter_world_states", "ix_world_states_project_chapter"):
        op.create_index("ix_world_states_project_chapter", "chapter_world_states", ["project_id", "chapter_number"], unique=False)
    if not _has_index("chapter_world_states", "ix_world_states_source_version"):
        op.create_index("ix_world_states_source_version", "chapter_world_states", ["source_version_id"], unique=False)
    if not _has_index("chapter_world_states", "ix_chapter_world_states_source_hash"):
        op.create_index("ix_chapter_world_states_source_hash", "chapter_world_states", ["source_hash"], unique=False)


def _add_chapter_columns() -> None:
    for table in ("chapter_outlines", "chapters"):
        if not _has_column(table, "volume_id"):
            # 已运行库的旧表用 nullable 列迁移，避免跨数据库 ALTER TABLE 加外键差异；
            # 新安装由 ORM metadata 直接创建完整外键约束。
            op.add_column(table, sa.Column("volume_id", _PK, nullable=True))
        if not _has_column(table, "sort_key"):
            op.add_column(table, sa.Column("sort_key", sa.Integer(), nullable=False, server_default="0"))
        if not _has_index(table, f"ix_{table}_volume_id"):
            op.create_index(f"ix_{table}_volume_id", table, ["volume_id"], unique=False)


def _backfill_legacy_volumes() -> None:
    if not (_has_table("novel_blueprints") and _has_column("novel_blueprints", "volumes")):
        return
    bind = op.get_bind()
    blueprints = bind.execute(sa.text("SELECT project_id, volumes FROM novel_blueprints")).mappings().all()
    known_fields = {
        "name", "start_chapter", "end_chapter", "arc_goal", "climax_hint",
        "status", "retrospective", "replan",
    }
    for blueprint in blueprints:
        project_id = blueprint["project_id"]
        existing = bind.execute(
            sa.text("SELECT id FROM volumes WHERE project_id = :project_id LIMIT 1"),
            {"project_id": project_id},
        ).first()
        if existing:
            continue
        position = 0
        for raw in _json_list(blueprint["volumes"]):
            start = _as_int(raw.get("start_chapter"))
            end = _as_int(raw.get("end_chapter"))
            if start is None or end is None or start < 1 or end < start:
                continue
            position += 1
            bind.execute(
                sa.text(
                    """
                    INSERT INTO volumes
                    (project_id, position, name, start_chapter, end_chapter, arc_goal, climax_hint,
                     status, retrospective, replan, extra)
                    VALUES
                    (:project_id, :position, :name, :start_chapter, :end_chapter, :arc_goal,
                     :climax_hint, :status, :retrospective, :replan, :extra)
                    """
                ),
                {
                    "project_id": project_id,
                    "position": position,
                    "name": str(raw.get("name") or ""),
                    "start_chapter": start,
                    "end_chapter": end,
                    "arc_goal": str(raw.get("arc_goal") or "") or None,
                    "climax_hint": str(raw.get("climax_hint") or "") or None,
                    "status": str(raw.get("status") or "planned"),
                    "retrospective": json.dumps(raw["retrospective"], ensure_ascii=False)
                    if isinstance(raw.get("retrospective"), dict) else None,
                    "replan": json.dumps(raw["replan"], ensure_ascii=False)
                    if isinstance(raw.get("replan"), dict) else None,
                    "extra": json.dumps({key: value for key, value in raw.items() if key not in known_fields}, ensure_ascii=False),
                },
            )


def _backfill_chapter_assignments() -> None:
    bind = op.get_bind()
    for table in ("chapter_outlines", "chapters"):
        bind.execute(
            sa.text(
                f"UPDATE {table} SET sort_key = chapter_number * 1000 "
                "WHERE sort_key IS NULL OR sort_key = 0"
            )
        )
    projects = bind.execute(sa.text("SELECT DISTINCT project_id FROM volumes")).mappings().all()
    for row in projects:
        project_id = row["project_id"]
        volumes = bind.execute(
            sa.text(
                "SELECT id, start_chapter, end_chapter FROM volumes "
                "WHERE project_id = :project_id ORDER BY position ASC"
            ),
            {"project_id": project_id},
        ).mappings().all()
        for volume in volumes:
            params = {
                "project_id": project_id,
                "volume_id": volume["id"],
                "start": volume["start_chapter"],
                "end": volume["end_chapter"],
            }
            for table in ("chapter_outlines", "chapters"):
                bind.execute(
                    sa.text(
                        f"UPDATE {table} SET volume_id = :volume_id "
                        "WHERE project_id = :project_id "
                        "AND chapter_number >= :start AND chapter_number <= :end"
                    ),
                    params,
                )


def upgrade() -> None:
    _create_tables()
    _add_chapter_columns()
    _backfill_legacy_volumes()
    _backfill_chapter_assignments()


def downgrade() -> None:
    for table in ("chapter_outlines", "chapters"):
        if _has_index(table, f"ix_{table}_volume_id"):
            op.drop_index(f"ix_{table}_volume_id", table_name=table)
        # batch_alter_table 兼容 SQLite 的 DROP COLUMN。
        with op.batch_alter_table(table) as batch_op:
            if _has_column(table, "volume_id"):
                batch_op.drop_column("volume_id")
            if _has_column(table, "sort_key"):
                batch_op.drop_column("sort_key")
    if _has_table("chapter_world_states"):
        op.drop_table("chapter_world_states")
    if _has_table("volumes"):
        op.drop_table("volumes")
