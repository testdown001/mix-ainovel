"""ForeshadowingAnalysis 回归测试（真实内存 SQLite）。

复现并锁定修复：analyze_foreshadowings 早期用 session.get(ForeshadowingAnalysis, project_id)
按主键查询，但该模型主键是自增 id、project_id 是 unique 普通列，导致恒返回 None →
每次新建 → 第二次调用必触发 project_id unique 约束冲突。

本用例对同一 project_id 连续调用两次，断言不抛异常且只存在一条分析记录。
这是仓库内首个使用真实 DB 引擎的集成测试，可作为后续主路径集成测试模板。
"""
import asyncio

# 必须导入以触发 SQLAlchemy mapper 完整注册（含 UserQuota 等），避免 mapper KeyError
import app.models  # noqa: F401
from app.models.foreshadowing import ForeshadowingAnalysis
from app.services.foreshadowing_service import ForeshadowingService

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _run():
    engine, Session = _make_sessionmaker()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    project_id = "proj-regression-1"
    async with Session() as session:  # type: AsyncSession
        service = ForeshadowingService(session)
        # 第一次调用：创建分析记录
        first = await service.analyze_foreshadowings(project_id)
        await session.commit()
        # 第二次调用：旧实现会因 unique 冲突崩溃，修复后应复用同一行
        second = await service.analyze_foreshadowings(project_id)
        await session.commit()

        assert first.project_id == project_id
        assert second.project_id == project_id

        rows = (
            await session.execute(
                select(ForeshadowingAnalysis).where(
                    ForeshadowingAnalysis.project_id == project_id
                )
            )
        ).scalars().all()
        # 关键断言：只有一条记录（复用而非重复插入）
        assert len(rows) == 1

    await engine.dispose()


def test_analyze_foreshadowings_twice_does_not_crash():
    asyncio.run(_run())
