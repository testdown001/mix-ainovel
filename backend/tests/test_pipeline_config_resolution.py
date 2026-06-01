"""PipelineConfigService.resolve_config 覆盖矩阵（真内存 SQLite）。

锁定最易出错的部分：preset 块 + 4 层覆写顺序（preset → settings →
writer_ultra_fast_mode → flow_config allowlist）。补齐核心主路径配置解析的回归保护。
"""
import asyncio

import app.models  # noqa: F401  触发 mapper 注册
from app.db.base import Base
from app.services.pipeline_config_service import PipelineConfigService

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _resolve(flow_config):
    engine, Session = _make_sessionmaker()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as session:
        config = await PipelineConfigService(session).resolve_config(flow_config)
    await engine.dispose()
    return config


def test_fast_preset_disables_heavy_postprocessing():
    config = asyncio.run(_resolve({"preset": "fast"}))
    assert config.preset == "fast"
    assert config.enable_fast_path is True
    assert config.version_count == 1
    assert config.enable_humanization is False
    assert config.enable_lightweight_humanization is True
    assert config.disable_guardrail_rewrite is True
    assert config.rag_mode == "simple"


def test_enhanced_preset_enables_worldbuilding_features():
    config = asyncio.run(_resolve({"preset": "enhanced"}))
    assert config.enable_constitution is True
    assert config.enable_persona is True
    assert config.enable_foreshadowing is True
    assert config.enable_faction is True
    assert config.enable_power_system is True
    assert config.enable_six_dimension is True


def test_literary_preset_enables_prose_pipeline():
    config = asyncio.run(_resolve({"preset": "literary"}))
    assert config.version_count == 1
    assert config.enable_scene_by_scene is True
    assert config.enable_prose_sculpting is True
    assert config.use_slim_prompt is True
    assert config.enable_memory is True


def test_flow_config_override_wins_over_preset():
    # fast preset 默认 enable_polish=False / enable_fast_path=True，
    # flow_config 显式覆写应生效（覆写顺序最后一层）。
    config = asyncio.run(
        _resolve({"preset": "fast", "enable_polish": True, "enable_fast_path": False})
    )
    assert config.enable_polish is True
    assert config.enable_fast_path is False


def test_two_stage_rag_mode_passthrough_is_accepted():
    # rag_mode=two_stage 仍被接受（解析为字符串），实际检索在
    # GenerationContextResolutionService 中回退到 simple。
    config = asyncio.run(_resolve({"preset": "fast", "rag_mode": "two_stage"}))
    assert config.rag_mode == "two_stage"
