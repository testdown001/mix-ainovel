# AIMETA P=数据库会话_异步会话工厂|R=异步会话_连接池|NR=不含查询逻辑|E=AsyncSessionLocal_get_db|X=internal|A=会话工厂|D=sqlalchemy|S=db|RD=./README.ai
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import settings

# MySQL 连接池参数：优化高并发场景的连接管理
# pool_size: 基础连接池大小，每个进程维护 20 个长连接
# max_overflow: 峰值时额外创建的连接数，最多 40 个
# pool_pre_ping: 每次使用前检查连接有效性，防止 MySQL gone away
# pool_recycle: 连接回收时间（秒），避免 MySQL 8 小时超时
# pool_timeout: 获取连接的超时时间（秒）
engine = create_async_engine(
    settings.sqlalchemy_database_uri,
    echo=settings.debug,
    pool_size=20,              # 基础连接池大小
    max_overflow=40,           # 峰值额外连接数
    pool_pre_ping=True,        # 连接健康检查
    pool_recycle=3600,         # 1 小时回收连接
    pool_timeout=30,           # 30 秒获取连接超时
    pool_use_lifo=True,        # LIFO 模式，优先复用最近使用的连接
)

# 统一的 Session 工厂，禁用 expire_on_commit 方便返回模型对象
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖项：提供一个作用域内共享的数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
