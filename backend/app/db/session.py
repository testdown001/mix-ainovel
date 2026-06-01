# AIMETA P=数据库会话_异步会话工厂|R=异步会话_连接池|NR=不含查询逻辑|E=AsyncSessionLocal_get_db|X=internal|A=会话工厂|D=sqlalchemy|S=db|RD=./README.ai
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from ..core.config import settings

_db_uri = settings.sqlalchemy_database_uri
_is_sqlite = "sqlite" in _db_uri

if _is_sqlite:
    engine = create_async_engine(
        _db_uri,
        echo=settings.debug,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # SQLite 默认不强制外键约束，需每个连接显式开启，
    # 否则 ondelete="CASCADE" 全部失效（删项目会留下孤儿行）。
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_async_engine(
        _db_uri,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
    )

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖项：提供一个作用域内共享的数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
