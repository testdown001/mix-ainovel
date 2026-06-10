"""章节生成预设档位门控（core/feature_gating）回归。

锁定两件事：
1. normalize_preset 的别名映射矩阵（与 resolve_config 共用同一张表）；
2. 旧名无法绕过档位门控（此前 _PRESET_FEATURES.get(别名) 查不到即放行）。
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.feature_gating import ensure_generation_preset_allowed, normalize_preset


def test_normalize_preset_matrix():
    assert normalize_preset(None) == "fast"
    assert normalize_preset("") == "fast"
    assert normalize_preset("fast") == "fast"
    assert normalize_preset(" Premium ") == "premium"
    assert normalize_preset("basic") == "standard"
    assert normalize_preset("enhanced") == "standard"
    assert normalize_preset("ultimate") == "premium"
    assert normalize_preset("platinum") == "premium"
    assert normalize_preset("literary") == "premium"
    # 未知名回退 fast：原样放行会同时绕过门控并落入未定义开关组合
    assert normalize_preset("custom") == "fast"
    assert normalize_preset("xpremium") == "fast"


def _gate(preset: str, tier: str) -> None:
    # load_min_tiers 对异常会回退代码默认档位，传哑 session 即可
    asyncio.run(ensure_generation_preset_allowed(SimpleNamespace(), preset, tier))


def test_alias_cannot_bypass_gate():
    # platinum → premium，free 档必须 403（修复前别名直接放行）
    with pytest.raises(HTTPException) as exc_info:
        _gate("platinum", "free")
    assert exc_info.value.status_code == 403

    # basic → standard，free 档 403、creator 档放行
    with pytest.raises(HTTPException):
        _gate("basic", "free")
    _gate("basic", "creator")


def test_canonical_gate_matrix():
    _gate("fast", "free")
    with pytest.raises(HTTPException):
        _gate("standard", "free")
    _gate("standard", "creator")
    with pytest.raises(HTTPException):
        _gate("premium", "creator")
    _gate("premium", "flagship")
    # 未知名归一化为 fast（免费档），放行且不会落入未定义配置
    _gate("nonexistent-preset", "free")


def test_batch_generate_endpoint_enforces_tier_gate(monkeypatch):
    """/advanced/batch-generate 与单章/异步入口同一套档位门控（曾是漏网入口）。"""
    import asyncio as _asyncio
    from types import SimpleNamespace as NS

    import app.services.quota_service as quota_service_module
    from app.api.routers import writer

    class _FakeQuotaService:
        def __init__(self, session):
            self.session = session

        async def get_or_create_quota(self, user_id):
            return NS(effective_tier="free")

    monkeypatch.setattr(quota_service_module, "QuotaService", _FakeQuotaService)

    request = NS(
        project_id="p1",
        chapter_numbers=[1, 2],
        writing_notes=None,
        flow_config=NS(preset="premium", model_dump=lambda: {"preset": "premium"}),
    )
    with pytest.raises(HTTPException) as exc_info:
        _asyncio.run(
            writer.batch_generate_chapters(
                request, session=SimpleNamespace(), current_user=NS(id=1)
            )
        )
    assert exc_info.value.status_code == 403


# ── flow_config 受控开关档位门控 ──

from app.core.feature_gating import (  # noqa: E402
    ensure_flow_overrides_allowed,
    load_flow_override_min_tiers,
)


def _flow_gate(flow_config, tier):
    asyncio.run(ensure_flow_overrides_allowed(SimpleNamespace(), flow_config, tier))


def test_flow_override_gate_matrix():
    # flagship 开关：free/creator 被拒，flagship 放行
    with pytest.raises(HTTPException) as exc_info:
        _flow_gate({"enable_optimizer": True}, "free")
    assert exc_info.value.status_code == 403
    with pytest.raises(HTTPException):
        _flow_gate({"enable_optimizer": True}, "creator")
    _flow_gate({"enable_optimizer": True}, "flagship")

    # creator 开关：free 被拒，creator 放行
    with pytest.raises(HTTPException):
        _flow_gate({"enable_polish": True}, "free")
    _flow_gate({"enable_polish": True}, "creator")


def test_flow_override_gate_only_blocks_explicit_true():
    # 关闭 / None / 缺省 / 未登记开关 / 空配置 一律放行
    _flow_gate({"enable_optimizer": False, "enable_polish": None}, "free")
    _flow_gate({"enable_fast_path": True, "disable_guardrail_rewrite": True}, "free")
    _flow_gate({}, "free")
    _flow_gate(None, "free")


def test_flow_override_min_tiers_loads_backend_override(monkeypatch):
    """后台 SystemConfig 覆写应改变生效档位（档位不是硬编码）。"""
    import app.repositories.system_config_repository as repo_module

    class _FakeRepo:
        def __init__(self, session):
            pass

        async def get_by_key(self, key):
            assert key == "feature_gating.flow_override_min_tiers"
            return SimpleNamespace(value='{"enable_optimizer": "creator", "bogus_key": "flagship", "enable_polish": "not_a_tier"}')

    monkeypatch.setattr(repo_module, "SystemConfigRepository", _FakeRepo)

    tiers = asyncio.run(load_flow_override_min_tiers(SimpleNamespace()))
    assert tiers["enable_optimizer"] == "creator"   # 合法覆写生效
    assert "bogus_key" not in tiers                  # 未登记键被忽略
    assert tiers["enable_polish"] == "creator"       # 非法档位值被忽略，保持默认

    # 覆写后 creator 即可显式开优化器
    _flow_gate({"enable_optimizer": True}, "creator")
