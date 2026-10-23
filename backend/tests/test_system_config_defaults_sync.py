"""启动时 SystemConfig 默认值同步（init_db._sync_system_config_defaults）回归。

锁定：新键补入、已有键只同步 description；多副本并发 INSERT 撞 IntegrityError 时
回滚后继续而不是让 lifespan 失败。
"""
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import init_db
from app.db.system_config_defaults import SYSTEM_CONFIG_DEFAULTS
from app.models.system_config import SystemConfig


@pytest.mark.asyncio
async def test_sync_inserts_missing_and_updates_description(db_session):
    db_session.add(SystemConfig(key="blueprint.backbone_enabled", value="false", description="旧说明"))
    await db_session.commit()

    await init_db._sync_system_config_defaults(db_session)
    await db_session.commit()

    row = await db_session.get(SystemConfig, "blueprint.backbone_enabled")
    assert row.value == "false"  # 已有值不动
    assert row.description != "旧说明"  # description 跟随代码
    review = await db_session.get(SystemConfig, "blueprint.review_enabled")
    assert review is not None and review.value == "true"


@pytest.mark.asyncio
async def test_sync_swallows_concurrent_duplicate(db_session, monkeypatch, caplog):
    calls = {"n": 0}
    original_flush = AsyncSession.flush

    async def racing_flush(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("INSERT", {}, Exception("1062 Duplicate entry"))
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", racing_flush)
    await init_db._sync_system_config_defaults(db_session)  # 不抛
    assert any("并发启动" in rec.getMessage() for rec in caplog.records)
    # 回滚后会话仍可用
    assert (await db_session.get(SystemConfig, "nonexistent")) is None
    assert len(SYSTEM_CONFIG_DEFAULTS) > 0


def test_every_default_description_fits_the_column():
    """description 是 VARCHAR(255)：超长在 MySQL 上报 1406 把启动打挂（2026-10-23 search.provider 实发 265 字）。"""
    from app.db.system_config_defaults import SYSTEM_CONFIG_DEFAULTS
    from app.models.system_config import SystemConfig

    limit = SystemConfig.description.type.length
    too_long = [(e.key, len(e.description or "")) for e in SYSTEM_CONFIG_DEFAULTS if len(e.description or "") > limit]
    assert not too_long, too_long


@pytest.mark.asyncio
async def test_sync_truncates_overlong_description_instead_of_failing(db_session, monkeypatch):
    from app.db import init_db
    from app.db.system_config_defaults import SystemConfigDefault
    from app.models.system_config import SystemConfig

    monkeypatch.setattr(init_db, "SYSTEM_CONFIG_DEFAULTS", [
        SystemConfigDefault(key="x.long", value_getter=lambda _: "1", description="说" * 300),
    ])
    await init_db._sync_system_config_defaults(db_session)
    await db_session.commit()
    row = await db_session.get(SystemConfig, "x.long")
    assert row is not None and len(row.description) == 255
