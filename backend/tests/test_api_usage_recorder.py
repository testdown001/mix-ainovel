"""API 用量记录器测试（真实内存 SQLite）。

锁定两件事：
1. estimate_tokens 的中英混合启发式（CJK≈1/字，其余≈1/4字符）。
2. record_usage 的可移植 upsert：同 (log_date, model, api_type) 多次记录会累加，
   不同 api_type 各自独立——这是后台用量统计真实生效的基础。
"""
import asyncio

import app.models  # noqa: F401  确保 mapper 完整注册
from app.models.api_usage_log import ApiUsageLog
from app.services.api_usage_recorder import estimate_tokens, record_usage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


def test_estimate_tokens_mixed():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    # 4 个 CJK + 4 个非 CJK：4 + 4/4 + 1 = 6
    assert estimate_tokens("中文测试abcd") == 6
    # 纯英文 8 字符：8/4 + 1 = 3
    assert estimate_tokens("abcdefgh") == 3


def test_record_usage_accumulates_and_isolates_api_type():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 同一 model+api_type 记录两次 → 应累加为一行
        async with Session() as s:
            await record_usage(s, model="gpt-x", api_type="default", prompt_tokens=10, completion_tokens=5)
        async with Session() as s:
            await record_usage(s, model="gpt-x", api_type="default", prompt_tokens=3, completion_tokens=2)
        # 不同 api_type → 独立行
        async with Session() as s:
            await record_usage(s, model="gpt-x", api_type="embedding", prompt_tokens=7, completion_tokens=0)

        async with Session() as s:
            rows = (await s.execute(select(ApiUsageLog).order_by(ApiUsageLog.api_type))).scalars().all()

        await engine.dispose()
        return rows

    rows = asyncio.run(_run())
    assert len(rows) == 2
    by_type = {r.api_type: r for r in rows}
    assert by_type["default"].prompt_tokens == 13
    assert by_type["default"].completion_tokens == 7
    assert by_type["default"].request_count == 2
    assert by_type["embedding"].prompt_tokens == 7
    assert by_type["embedding"].request_count == 1
