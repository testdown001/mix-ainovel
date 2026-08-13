"""Reranker 配置改走 SystemConfig（后台可配 + 可测）的回归测试。

背景（2026-08-01）：重排此前是唯一还只读 env 的检索侧通道，改配置必须改 .env 并重启，
生产上因此长期指着一个 503 的地址空转。现统一为「SystemConfig 优先 → env 兜底」，
与 llm.*/embedding.* 同口径，并在后台「接口管理」提供开关与「测试连接」。

本文件锁住三处最容易回归的地方：
1. 开关是**字符串**存在 DB 里，必须按布尔语义解析——`"false"` 是关闭，不能「非空即真」；
2. SystemConfig 必须压过 env，否则后台改了不生效（等于没做）；
3. 地址自动补 `/rerank` 与「留空回退 embedding 配置」的旧兼容行为不能丢。
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict
from unittest.mock import patch

import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError
import app.utils.rerank_utils as ru


def _patch_system_configs(values: Dict[str, str]):
    """把 SystemConfig 表桩成给定的 key→value 映射。

    _load_config 用一条 IN 查询取全部键，这里照同样形状返回 (key, value) 行。
    """

    class _Rows:
        def all(self):
            return list(values.items())

    class _Session:
        async def execute(self, *_a, **_k):
            return _Rows()

    @asynccontextmanager
    async def _factory():
        yield _Session()

    import app.db.session as db_session

    return patch.object(db_session, "AsyncSessionLocal", _factory)


def _load(values: Dict[str, str]):
    with _patch_system_configs(values):
        return asyncio.run(ru._load_config())


# --------------------------------------------------------------------------
# 1. 布尔解析
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stored,expected",
    [("true", True), ("True", True), ("1", True), ("on", True),
     ("false", False), ("False", False), ("0", False), ("", False)],
)
def test_enabled_parses_boolean_semantics(stored, expected):
    """DB 里存的是字符串，`"false"` 必须关闭——若按「非空即真」判，后台永远关不掉。"""
    values = {"rerank.enabled": stored} if stored else {}
    with _patch_system_configs(values), \
            patch.object(ru.settings, "rag_reranker_enabled", False):
        assert asyncio.run(ru.is_rerank_enabled()) is expected


def test_enabled_falls_back_to_env_when_unset():
    """DB 无该键时沿用 env 种子值，升级前后行为一致。"""
    with _patch_system_configs({}), patch.object(ru.settings, "rag_reranker_enabled", True):
        assert asyncio.run(ru.is_rerank_enabled()) is True


# --------------------------------------------------------------------------
# 2. SystemConfig 优先于 env
# --------------------------------------------------------------------------

def test_system_config_overrides_env():
    with patch.object(ru.settings, "rag_reranker_api_url", "https://from-env.example.com/v1"), \
            patch.object(ru.settings, "rag_reranker_api_key", "env-key"), \
            patch.object(ru.settings, "rag_reranker_model", "env-model"), \
            _patch_system_configs({
                "rerank.api_url": "https://from-db.example.com/v1",
                "rerank.api_key": "db-key",
                "rerank.model": "db-model",
            }):
        url, key, model = asyncio.run(ru._resolve_rerank_config())

    assert url == "https://from-db.example.com/v1"  # 原样使用
    assert key == "db-key"
    assert model == "db-model"


def test_env_used_when_system_config_absent():
    with patch.object(ru.settings, "rag_reranker_api_url", "https://from-env.example.com/v1"), \
            patch.object(ru.settings, "rag_reranker_api_key", "env-key"), \
            _patch_system_configs({}):
        url, key, _ = asyncio.run(ru._resolve_rerank_config())

    assert url == "https://from-env.example.com/v1"  # 原样使用
    assert key == "env-key"


# --------------------------------------------------------------------------
# 3. 端点拼接与 embedding 回退
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "configured,expected",
    [
        # 各家 rerank 路径不一样，管理员填什么就用什么，只去掉末尾斜杠
        ("https://api.jina.ai/v1/rerank", "https://api.jina.ai/v1/rerank"),
        ("https://api.jina.ai/v1/rerank/", "https://api.jina.ai/v1/rerank"),
        ("https://router.tumuer.me/v1/rerank/multimodal", "https://router.tumuer.me/v1/rerank/multimodal"),
        ("https://host/custom/path", "https://host/custom/path"),
        # 即使看起来像基础地址也不擅自补——猜错比不猜更糟
        ("https://api.jina.ai/v1", "https://api.jina.ai/v1"),
    ],
)
def test_admin_supplied_url_is_used_verbatim(configured, expected):
    """后台填的地址原样使用。

    历史事故（2026-08-01）：填 `…/v1/rerank/multimodal` 被自动补成
    `…/v1/rerank/multimodal/rerank` → 404。自动补 /rerank 只该用于
    「没填地址、退回借 embedding base_url」那条推导路径。
    """
    with _patch_system_configs({"rerank.api_url": configured, "rerank.api_key": "k"}):
        url, _, _ = asyncio.run(ru._resolve_rerank_config())
    assert url == expected


def test_falls_back_to_embedding_config_when_rerank_unset():
    """旧部署没有专用 rerank 配置时仍借用 embedding 配置（兼容行为不能丢）。"""
    with patch.object(ru.settings, "rag_reranker_api_url", None), \
            patch.object(ru.settings, "rag_reranker_api_key", None), \
            _patch_system_configs({
                "embedding.base_url": "https://emb.example.com/v1",
                "embedding.api_key": "emb-key",
            }):
        url, key, _ = asyncio.run(ru._resolve_rerank_config())
        status = asyncio.run(ru.get_rerank_runtime_status())

    assert url == "https://emb.example.com/v1/rerank"
    assert key == "emb-key"
    assert status["config_source"] == "embedding_fallback"


def test_unconfigured_reports_unconfigured():
    with patch.object(ru.settings, "rag_reranker_api_url", None), \
            patch.object(ru.settings, "rag_reranker_api_key", None), \
            patch.object(ru.settings, "embedding_base_url", None), \
            patch.object(ru.settings, "embedding_api_key", None), \
            _patch_system_configs({}):
        status = asyncio.run(ru.get_rerank_runtime_status())

    assert status["config_source"] == "unconfigured"
    assert status["api_url"] is None
    assert status["api_key_configured"] is False


# --------------------------------------------------------------------------
# 4. 「测试连接」按钮
# --------------------------------------------------------------------------

def test_connection_test_ok_and_clears_latch():
    """测试成功要顺手解除熄火——管理员刚验证过是最可靠的恢复信号。"""
    url = "https://ok.example.com/v1/rerank"
    ru._rerank_failures[url] = ru._RERANK_FAILURE_THRESHOLD

    async def _fake_post(*_a, **_k):
        return {"results": [{"index": 0, "relevance_score": 0.9}]}

    with _patch_system_configs({
        "rerank.enabled": "true", "rerank.api_url": url, "rerank.api_key": "k", "rerank.model": "m",
    }), patch.object(ru, "_post_rerank", _fake_post):
        result = asyncio.run(ru.test_rerank_connection())

    assert result["ok"] is True
    assert result["model"] == "m"
    assert url not in ru._rerank_failures


def test_connection_test_reports_failure_without_raising():
    async def _boom(*_a, **_k):
        raise RuntimeError("503 Service Unavailable")

    with _patch_system_configs({
        "rerank.enabled": "true",
        "rerank.api_url": "https://dead.example.com/v1",
        "rerank.api_key": "k",
    }), patch.object(ru, "_post_rerank", _boom):
        result = asyncio.run(ru.test_rerank_connection())

    assert result["ok"] is False
    assert "503" in result["detail"]


def test_connection_test_warns_when_switch_is_off():
    """地址可用但开关关着，必须在 detail 里说清，否则管理员会以为已经生效。"""
    async def _fake_post(*_a, **_k):
        return {"results": [{"index": 0, "relevance_score": 0.9}]}

    with _patch_system_configs({
        "rerank.enabled": "false",
        "rerank.api_url": "https://ok.example.com/v1",
        "rerank.api_key": "k",
    }), patch.object(ru, "_post_rerank", _fake_post):
        result = asyncio.run(ru.test_rerank_connection())

    assert result["ok"] is True
    assert "关闭" in result["detail"]


def test_connection_test_unconfigured_is_not_ok():
    with patch.object(ru.settings, "rag_reranker_api_url", None), \
            patch.object(ru.settings, "rag_reranker_api_key", None), \
            patch.object(ru.settings, "embedding_base_url", None), \
            patch.object(ru.settings, "embedding_api_key", None), \
            _patch_system_configs({}):
        result = asyncio.run(ru.test_rerank_connection())

    assert result["ok"] is False
    assert "未配置" in result["detail"]


# --------------------------------------------------------------------------
# 5. 后台入口接线
# --------------------------------------------------------------------------

def test_rerank_is_a_testable_admin_channel():
    """后台「测试连接」与「通道诊断」都必须认识 rerank，否则按钮 400。"""
    from app.api.routers.admin import _HEALTH_CHANNELS, _TESTABLE_CHANNELS

    assert "rerank" in _TESTABLE_CHANNELS
    assert "rerank" in _HEALTH_CHANNELS


def test_disabled_switch_still_tests_but_reports_unconfigured():
    """开关关闭时仍要真实发起调用（管理员的流程是「先测通再打开开关」），
    但 configured 必须为 False——检索实际不会重排，后台不能显示成「可用」。"""
    async def _fake_post(*_a, **_k):
        return {"results": [{"index": 0, "relevance_score": 0.9}]}

    values = {
        "rerank.enabled": "false",
        "rerank.api_url": "https://vendor.example/v1/rerank",
        "rerank.api_key": "sk-r",
        "rerank.model": "bge",
    }
    with _patch_system_configs(values), \
            patch.object(ru.settings, "rag_reranker_enabled", False), \
            patch.object(ru, "_post_rerank", _fake_post):
        result = asyncio.run(ru.test_rerank_connection())

    assert result["ok"] is True          # 地址密钥是通的
    assert result["configured"] is False  # 但开关没开
    assert "开关为关闭状态" in result["detail"]


def test_llm_service_test_channel_delegates_to_rerank_utils():
    from app.services.llm_service import LLMService

    async def _fake():
        return {"ok": True, "model": "m", "latency_ms": 1, "detail": "ok"}

    svc = LLMService.__new__(LLMService)
    with patch.object(ru, "test_rerank_connection", _fake):
        assert asyncio.run(svc.test_channel("rerank"))["ok"] is True


def test_rerank_keys_are_seeded_from_env():
    """首次启动要把 env 值播进 SystemConfig，升级后后台里不能是空白。"""
    from app.db.system_config_defaults import SYSTEM_CONFIG_DEFAULTS

    keys = {d.key for d in SYSTEM_CONFIG_DEFAULTS}
    assert {"rerank.enabled", "rerank.api_url", "rerank.api_key", "rerank.model"} <= keys
