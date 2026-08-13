"""后台「测试通道」的启用判据必须与运行时解析一致。

2026-08-13 线上实测暴露：评分通道四个键全空（运行时 get_grader_llm_response 抛
「未配置」→ 证据打分静默跳过），但后台健康表显示「✅ 可用 deepseek-v4-flash」——
因为 test_channel 只看 api_key，一空就拿 llm.* 的 key 去测，等于用默认通道
冒名顶替了一条实际禁用的通道。管理员看到全绿，用户那边能力压根不存在。

契约：
- 搜索/评分未显式配置（四键全空）→ configured=False，不发任何请求；
- 只填 model（api_key 留空继承 llm.*）也算启用 → 会真的发请求；
- 润色未单独配置时确实复用默认通道 → configured=True（测的正是运行时会走的配置）；
- 兜底必须独立 api_key，否则未启用。
"""
import asyncio
from unittest.mock import patch

import pytest

from app.services.llm_service import LLMService, channel_explicitly_configured


def _svc(config: dict) -> LLMService:
    """不走 __init__（它要 session），只桩掉配置读取。"""
    svc = LLMService.__new__(LLMService)

    async def _get(key: str):
        return config.get(key)

    svc._get_config_value = _get  # type: ignore[method-assign]
    return svc


def _run(svc: LLMService, channel: str) -> dict:
    return asyncio.run(svc.test_channel(channel))


class _CallRecorder:
    """记录是否真的发起了 LLM 调用，以及用的是哪套配置。"""

    def __init__(self, response: str = "ok"):
        self.calls: list = []
        self.response = response

    async def __call__(self, messages, **kwargs):
        self.calls.append(kwargs.get("config_override"))
        return self.response


# ----------------------------------------------------------- 共用判据


def test_predicate_any_field_counts():
    assert channel_explicitly_configured(None, None, None, None) is False
    assert channel_explicitly_configured("", "", "", "") is False
    assert channel_explicitly_configured(None, None, "some-model", None) is True
    assert channel_explicitly_configured("sk-x", None, None, None) is True


# ----------------------------------------------------------- 搜索/评分门控


@pytest.mark.parametrize("channel", ["search", "grader"])
def test_optional_channel_all_blank_reports_unconfigured_without_calling(channel):
    """核心回归：四键全空时不得拿默认通道的 key 去测，更不得报「可用」。"""
    recorder = _CallRecorder()
    svc = _svc({"llm.api_key": "sk-default", "llm.base_url": "https://d/v1", "llm.model": "d-model"})
    with patch.object(LLMService, "_stream_and_collect", recorder):
        result = _run(svc, channel)

    assert result["configured"] is False
    assert result["ok"] is False
    assert recorder.calls == []  # 一次请求都不该发
    assert result["model"] == ""  # 不得回显默认通道的模型名，避免误认为已配置


@pytest.mark.parametrize("channel,prefix", [("search", "llm_search"), ("grader", "llm_grader")])
def test_optional_channel_model_only_is_enabled_and_inherits_default_key(channel, prefix):
    """只填 model、api_key 留空继承 llm.*——运行时视为启用，测试也必须真的发请求。"""
    recorder = _CallRecorder()
    svc = _svc({
        "llm.api_key": "sk-default",
        "llm.base_url": "https://d/v1",
        "llm.model": "d-model",
        f"{prefix}.model": "tiny-model",
    })
    with patch.object(LLMService, "_stream_and_collect", recorder):
        result = _run(svc, channel)

    assert result["configured"] is True
    assert result["ok"] is True
    assert len(recorder.calls) == 1
    override = recorder.calls[0]
    assert override["model"] == "tiny-model"
    assert override["api_key"] == "sk-default"  # 继承默认 key
    assert override["base_url"] == "https://d/v1"


@pytest.mark.parametrize("channel,prefix", [("search", "llm_search"), ("grader", "llm_grader")])
def test_optional_channel_unreachable_is_configured_but_not_ok(channel, prefix):
    """「配了但连不通」与「没配」是两种状态，不能混为一谈。"""
    async def _boom(_self, messages, **kwargs):  # patch 到类上会绑定 self
        raise RuntimeError("upstream 503")

    svc = _svc({"llm.api_key": "sk-d", f"{prefix}.api_key": "sk-own", f"{prefix}.model": "m"})
    with patch.object(LLMService, "_stream_and_collect", _boom):
        result = _run(svc, channel)

    assert result["configured"] is True
    assert result["ok"] is False
    assert "503" in result["detail"]


# ----------------------------------------------------------- 润色/兜底/默认


def test_polish_without_own_config_reuses_default_and_counts_as_configured():
    """润色未单独配置时运行时确实复用默认通道，所以它是「已配置」。"""
    recorder = _CallRecorder()
    svc = _svc({"llm.api_key": "sk-default", "llm.base_url": "https://d/v1", "llm.model": "d-model"})
    with patch.object(LLMService, "_stream_and_collect", recorder):
        result = _run(svc, "polish")

    assert result["configured"] is True
    assert result["ok"] is True
    assert recorder.calls[0]["api_key"] == "sk-default"


def test_polish_unconfigured_everywhere_is_unconfigured():
    svc = _svc({})
    result = _run(svc, "polish")
    assert result["configured"] is False
    assert result["ok"] is False


def test_fallback_requires_own_api_key():
    """兜底不独立配 key 就是没启用（与 _resolve_fallback_llm_config 一致）。"""
    svc = _svc({"llm.api_key": "sk-default", "llm.model": "d-model"})
    result = _run(svc, "fallback")
    assert result["configured"] is False
    assert "无处可退" in result["detail"]


def test_fallback_inherits_base_and_model_when_key_present():
    recorder = _CallRecorder()
    svc = _svc({
        "llm.api_key": "sk-d", "llm.base_url": "https://d/v1", "llm.model": "d-model",
        "llm_fallback.api_key": "sk-fb",
    })
    with patch.object(LLMService, "_stream_and_collect", recorder):
        result = _run(svc, "fallback")

    assert result["configured"] is True
    override = recorder.calls[0]
    assert override["api_key"] == "sk-fb"
    assert override["base_url"] == "https://d/v1"
    assert override["model"] == "d-model"


def test_default_channel_unconfigured():
    svc = _svc({})
    result = _run(svc, "default")
    assert result["configured"] is False
    assert result["ok"] is False


# ----------------------------------------------------------- rerank


def test_rerank_configured_comes_from_rerank_utils():
    """重排的启用判据归 rerank_utils（它才知道 enabled 与回退来源），test_channel 只转发。"""
    async def _fake():
        return {"ok": True, "configured": False, "model": "bge", "latency_ms": 5,
                "detail": "重排正常；⚠️ 当前开关为关闭状态"}

    with patch("app.utils.rerank_utils.test_rerank_connection", _fake):
        result = _run(_svc({}), "rerank")

    assert result["configured"] is False
    assert result["ok"] is True  # 地址密钥是通的，只是开关没开


def test_rerank_result_without_configured_defaults_to_true():
    async def _fake():
        return {"ok": True, "model": "bge", "latency_ms": 5, "detail": "重排正常"}

    with patch("app.utils.rerank_utils.test_rerank_connection", _fake):
        result = _run(_svc({}), "rerank")

    assert result["configured"] is True


def test_unknown_channel_is_unconfigured():
    result = _run(_svc({}), "nope")
    assert result["configured"] is False
    assert "未知通道" in result["detail"]
