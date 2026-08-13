"""think/推理模型兼容性判定的单元测试。

锁定：
- Claude thinking 模型识别（统一判定，避免 _stream_and_collect / chat_with_tools 两处漂移）。
- OpenAI o 系列推理模型识别（含 -mini/-preview 与 provider 前缀）。
- "temperature/top_p 不被支持"的 400 错误识别（推理模型自动剔参重试的触发条件）。
"""
import app.models  # noqa: F401
from app.services.llm_service import LLMService


def test_claude_thinking_detection():
    assert LLMService._is_claude_thinking_model("claude-opus-4-20250514")
    assert LLMService._is_claude_thinking_model("claude-sonnet-4-6")
    assert LLMService._is_claude_thinking_model("claude-3-7-sonnet")
    assert not LLMService._is_claude_thinking_model("claude-3-5-sonnet")
    assert not LLMService._is_claude_thinking_model("gpt-4o")
    assert not LLMService._is_claude_thinking_model(None)


def test_openai_reasoning_detection():
    for name in ["o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini", "openai/o3-mini", "o3.5"]:
        assert LLMService._is_openai_reasoning_model(name), name
    for name in ["gpt-4o", "gpt-5", "gpt-4o-mini", "omni-model", "claude-opus-4", "", None]:
        assert not LLMService._is_openai_reasoning_model(name), name


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    @property
    def text(self):
        import json as _json
        return _json.dumps(self._payload)


class _FakeError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.response = _FakeResp({"error": {"message": message}})


def test_temperature_unsupported_error_detection():
    # OpenAI o 系列的典型报错
    assert LLMService._is_temperature_unsupported_error(
        _FakeError("Unsupported value: 'temperature' does not support 0.7 with this model. Only the default (1) value is supported.")
    )
    assert LLMService._is_temperature_unsupported_error(_FakeError("top_p is not supported for this model"))
    assert LLMService._is_temperature_unsupported_error(_FakeError("该模型不支持 temperature 参数"))
    # 非 temperature 类错误不应误判
    assert not LLMService._is_temperature_unsupported_error(_FakeError("response_format json_object is invalid"))
    assert not LLMService._is_temperature_unsupported_error(_FakeError("rate limit exceeded"))
    assert not LLMService._is_temperature_unsupported_error(_FakeError(""))


def test_max_completion_tokens_and_stream_options_error_detection():
    assert LLMService._is_max_completion_tokens_error(
        _FakeError("Use 'max_completion_tokens' instead of 'max_tokens'")
    )
    assert not LLMService._is_max_completion_tokens_error(_FakeError("max_tokens too large"))
    assert LLMService._is_stream_options_unsupported_error(
        _FakeError("stream_options is not supported")
    )
    assert not LLMService._is_stream_options_unsupported_error(_FakeError("temperature unsupported"))


def test_build_extra_kwargs_gating():
    b = LLMService._build_stream_extra_kwargs
    # reasoning_effort 仅 openai/responses 格式
    assert b("openai", thinking_budget=None, disable_thinking=False,
             reasoning_effort="high", model_name="o3-mini", enable_usage=True) == {
        "reasoning_effort": "high", "enable_usage": True}
    # 2026-08-14 起不再按模型名判断：门槛原本是「o 系列 or gpt-5」，用来避免普通模型
    # 因未知参数 400；代价是 DeepSeek/Grok/GLM 这类同样默认深度思考的模型永远收不到
    # 推理档，后台配了也无效（实测一章约四分之一时间耗在这些调用的推理 token 上）。
    # 现在改为「先试，被上游拒绝就按 base_url|model 记闩并去掉重试」，普通模型的成本
    # 是每进程每上游组合一次多余往返。判据见 reasoning_effort_supported 参数。
    assert b("openai", thinking_budget=None, disable_thinking=False,
             reasoning_effort="high", model_name="gpt-4o") == {"reasoning_effort": "high"}
    assert "reasoning_effort" not in b(
        "openai", thinking_budget=None, disable_thinking=False,
        reasoning_effort="high", model_name="gpt-4o", reasoning_effort_supported=False,
    )
    # gpt-5 走 responses 支持 effort
    assert b("openai-responses", thinking_budget=None, disable_thinking=False,
             reasoning_effort="medium", model_name="gpt-5") == {"reasoning_effort": "medium"}
    # anthropic 不受影响（仅 thinking_budget）
    assert b("anthropic", thinking_budget=2000, disable_thinking=False,
             reasoning_effort="high", model_name="claude-opus-4") == {"thinking_budget": 2000}
    # 非法 effort 值忽略
    assert "reasoning_effort" not in b("openai", thinking_budget=None, disable_thinking=False,
                                       reasoning_effort="ultra", model_name="o3")
