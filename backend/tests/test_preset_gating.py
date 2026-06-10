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
    # 未知名原样返回，交由配置层兜底
    assert normalize_preset("custom") == "custom"


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
    # 未知名放行（不归任何能力管）
    _gate("nonexistent-preset", "free")
