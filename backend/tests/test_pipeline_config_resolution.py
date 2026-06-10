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


def test_enhanced_alias_maps_to_standard_with_worldbuilding():
    # 旧名 enhanced → standard（入口归一化，不再递归）
    config = asyncio.run(_resolve({"preset": "enhanced"}))
    assert config.preset == "standard"
    assert config.enable_constitution is True
    assert config.enable_persona is True
    assert config.enable_foreshadowing is True
    assert config.enable_faction is True
    assert config.enable_power_system is True
    assert config.enable_six_dimension is True


def test_literary_alias_maps_to_premium():
    # 旧名 literary → premium（2026-06 三档收敛后的官方映射）；
    # 场景化分步分支不再随任何 preset 默认开启，只能 flow_config 显式覆写。
    config = asyncio.run(_resolve({"preset": "literary"}))
    assert config.preset == "premium"
    assert config.version_count == 1
    assert config.enable_memory is True
    assert config.enable_self_critique is True
    assert config.enable_reader_sim is True
    assert config.enable_scene_by_scene is False


def test_legacy_alias_matrix_resolves_without_recursion():
    expected = {
        "basic": "standard",
        "enhanced": "standard",
        "ultimate": "premium",
        "platinum": "premium",
        "literary": "premium",
    }
    for alias, canonical in expected.items():
        config = asyncio.run(_resolve({"preset": alias}))
        assert config.preset == canonical, f"alias={alias}"


def test_omitted_preset_defaults_to_fast():
    config = asyncio.run(_resolve({}))
    assert config.preset == "fast"
    assert config.enable_fast_path is True


def test_unknown_preset_falls_back_to_fast():
    # 未知名不得落入"无 preset 块约束"的未定义开关组合
    config = asyncio.run(_resolve({"preset": "xpremium"}))
    assert config.preset == "fast"
    assert config.enable_fast_path is True
    assert config.version_count == 1


def test_requested_versions_capped():
    # versions 直接放大 LLM 成本，请求侧上限 5（standard 不强制单版本，适合验证）
    config = asyncio.run(_resolve({"preset": "standard", "versions": 50}))
    assert config.version_count == 5


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
