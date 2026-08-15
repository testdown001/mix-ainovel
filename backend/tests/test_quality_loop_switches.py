"""质量回路四开关迁到 SystemConfig（后台可随时开关，2026-08-01）。

这四项原本是纯 env 开关（OUTLINE_REVISION_ENABLED 等），改一次要编辑 deploy/.env
并重建容器——运行时业务配置本就该进 SystemConfig（同 rerank.*、llm.*）。

锁三件事：
1. 布尔按语义解析——DB 里存的是字符串，`"false"` 必须是关闭，不能「非空即真」，
   否则后台永远关不掉（与 rerank 迁移时踩过的同一个坑）；
2. SystemConfig 必须压过 env，否则后台改了不生效 = 等于没做；
3. 默认全关，且只在 premium 档生效（flagship 独占）。
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict
from unittest.mock import patch

import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.services.pipeline_config_service import PipelineConfig, PipelineConfigService

_ALL = ("outline_revision", "volume_retrospective", "two_pass_draft", "character_significance")


def _service(stored: Dict[str, str]):
    """把 SystemConfig 表桩成给定映射（_load_quality_loop_switches 用一条 IN 查询取全部键）。"""

    class _Rows:
        def all(self):
            return [(f"quality_loop.{k}", v) for k, v in stored.items()]

    class _Session:
        async def execute(self, *_a, **_k):
            return _Rows()

    return PipelineConfigService(_Session())


def _load(stored: Dict[str, str], env: Dict[str, bool] | None = None):
    svc = _service(stored)
    from app.services import pipeline_config_service as mod

    patches = []
    for name, value in (env or {}).items():
        patches.append(patch.object(mod.settings, f"{name}_enabled", value))
    for p in patches:
        p.start()
    try:
        return asyncio.run(svc._load_quality_loop_switches())
    finally:
        for p in patches:
            p.stop()


# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stored,expected",
    [("true", True), ("True", True), ("1", True), ("on", True),
     ("false", False), ("False", False), ("0", False)],
)
def test_boolean_semantics(stored, expected):
    """`"false"` 必须解析为关闭——按「非空即真」判会导致后台永远关不掉。"""
    values = _load({"two_pass_draft": stored}, env={"two_pass_draft": False})
    assert values["two_pass_draft"] is expected


def test_system_config_overrides_env():
    values = _load(
        {"outline_revision": "false", "character_significance": "true"},
        env={"outline_revision": True, "character_significance": False},
    )
    assert values["outline_revision"] is False       # DB 关掉压过 env 开着
    assert values["character_significance"] is True  # DB 开着压过 env 关掉


def test_env_used_when_key_absent():
    """DB 里没有该键时沿用 env 种子值，升级前后行为一致。"""
    values = _load({}, env={"volume_retrospective": True, "two_pass_draft": False})
    assert values["volume_retrospective"] is True
    assert values["two_pass_draft"] is False


def test_db_failure_falls_back_to_env_without_raising():
    """DB 不可用不得阻断生成——静默退回 env。"""

    class _BoomSession:
        async def execute(self, *_a, **_k):
            raise RuntimeError("DB 挂了")

    svc = PipelineConfigService(_BoomSession())
    values = asyncio.run(svc._load_quality_loop_switches())
    assert set(values) == set(_ALL)
    assert all(isinstance(v, bool) for v in values.values())


def test_all_four_switches_default_off():
    config = PipelineConfig()
    assert config.enable_outline_revision is False
    assert config.enable_volume_retrospective is False
    assert config.enable_two_pass_draft is False
    assert config.enable_character_significance is False


def test_describe_quality_loops_off_for_fast_free():
    svc = _service({"outline_revision": "true", "two_pass_draft": "true"})
    desc = asyncio.run(svc.describe_quality_loops(preset="fast", tier="free"))
    assert desc["preset"] == "fast"
    assert all(item["active"] is False for item in desc["loops"].values())
    assert desc["loops"]["outline_revision"]["system"] is True
    # 旗舰 + flow_config 才能在非 premium 上打开
    flagged = asyncio.run(
        svc.describe_quality_loops(
            preset="fast",
            tier="flagship",
            flow_config={"enable_outline_revision": True},
        )
    )
    assert flagged["loops"]["outline_revision"]["active"] is True
    assert flagged["loops"]["two_pass_draft"]["active"] is False


def test_switches_are_seeded_into_system_config():
    """首次启动要把 env 值播进 SystemConfig，升级后后台里不能是空白。"""
    from app.db.system_config_defaults import SYSTEM_CONFIG_DEFAULTS

    keys = {d.key for d in SYSTEM_CONFIG_DEFAULTS}
    assert {f"quality_loop.{name}" for name in _ALL} <= keys


def test_seeded_entries_carry_cost_warning_for_two_pass():
    """两遍制是唯一在生成链路内、成本翻倍的一项，描述里必须写明，
    否则管理员会把它当成和前三项一样的「免费增强」随手打开。"""
    from app.db.system_config_defaults import SYSTEM_CONFIG_DEFAULTS

    entry = next(d for d in SYSTEM_CONFIG_DEFAULTS if d.key == "quality_loop.two_pass_draft")
    assert "翻倍" in (entry.description or "")
