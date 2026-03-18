# AIMETA P=数据库会话_异步会话工厂|R=异步会话_连接池|NR=不含查询逻辑|E=AsyncSessionLocal_get_db|X=internal|A=会话工厂|D=sqlalchemy|S=db|RD=./README.ai
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from ..core.config import settings

# 根据数据库类型选择不同的连接池配置
_is_sqlite = settings.db_provider == "sqlite" or "sqlite" in settings.sqlalchemy_database_uri

if _is_sqlite:
    # SQLite 不支持并发写入，使用 StaticPool 单连接
    engine = create_async_engine(
        settings.sqlalchemy_database_uri,
        echo=settings.debug,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
else:
    # MySQL 连接池参数：优化高并发场景的连接管理
    engine = create_async_engine(
        settings.sqlalchemy_database_uri,
        echo=settings.debug,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
        pool_use_lifo=True,
    )

# 统一的 Session 工厂，禁用 expire_on_commit 方便返回模型对象
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖项：提供一个作用域内共享的数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
