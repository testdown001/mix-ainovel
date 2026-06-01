"""Alembic 迁移环境（异步引擎版）。

设计要点：
- 直接复用 app.core.config.settings.sqlalchemy_database_uri，与应用运行时同一连接配置；
- 通过 create_async_engine + run_sync 支持 aiosqlite / asyncmy，无需额外同步驱动；
- target_metadata 取 app.db.base.Base.metadata，导入 app.models 触发全部表注册。
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# 确保所有 ORM 模型被导入，从而填充 Base.metadata
import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    return settings.sqlalchemy_database_uri


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连接数据库。"""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite 需 batch 模式做 ALTER
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    connectable = create_async_engine(_get_url(), poolclass=NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
