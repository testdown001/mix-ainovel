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
