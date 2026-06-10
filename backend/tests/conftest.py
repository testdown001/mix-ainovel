"""共享测试 fixture。

db_session：真内存 SQLite 异步会话（StaticPool 保证同一连接），供
@pytest.mark.asyncio 风格的集成测试使用（需 pytest-asyncio，CI 已随
pytest 一并安装）。其余测试沿用各自文件内的 asyncio.run 模式，不受影响。
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  触发全部 mapper 注册
from app.db.base import Base


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()
