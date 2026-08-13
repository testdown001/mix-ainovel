"""推理档下发与自愈回退。

背景（2026-08-14 线上实测）：标准档一章 203s，其中约 55s 花在辅助调用的推理 token 上
（一次一致性检查为 2504 字 JSON 烧掉 8257 个推理 token）。根因是 reasoning_effort 只在
模型名匹配 o 系列/gpt-5 时才下发，DeepSeek/Grok 这类同样默认深度思考的模型永远收不到，
后台配了也等于没配。这里锁住三件事：
1. 下发不再看模型名（openai 兼容格式一律尝试）；
2. 上游拒绝该参数时按 base_url|model 记闩并去掉重试，不影响可用性；
3. 结构化 JSON 调用降档、正文创作不降档（付费档位差异不被削弱）。
"""
import pytest

from app.services.llm_service import LLMService


def _kwargs(model: str, effort: str = "high", *, supported: bool = True, fmt: str = "openai"):
    return LLMService._build_stream_extra_kwargs(
        fmt,
        thinking_budget=None,
        disable_thinking=False,
        reasoning_effort=effort,
        model_name=model,
        reasoning_effort_supported=supported,
    )


class TestEffortForwarding:
    @pytest.mark.parametrize(
        "model",
        ["deepseek-v4-flash", "grok-4.5", "glm-4.6", "qwen-max", "o3-mini", "gpt-5.4"],
    )
    def test_forwarded_regardless_of_model_name(self, model):
        """曾经只有 o 系列/gpt-5 能拿到推理档，其余思考型模型被名字门槛挡掉。"""
        assert _kwargs(model)["reasoning_effort"] == "high"

    def test_latched_target_drops_param(self):
        """已知不接受该参数的上游组合：直接不带，避免每次都白费一次往返。"""
        assert "reasoning_effort" not in _kwargs("gpt-4o-mini", supported=False)

    def test_only_openai_compatible_formats(self):
        for fmt in ("anthropic", "gemini", "anyrouter"):
            assert "reasoning_effort" not in _kwargs("claude-opus-4", fmt=fmt)

    def test_responses_format_forwarded(self):
        assert _kwargs("gpt-5.4", fmt="openai-responses")["reasoning_effort"] == "high"

    @pytest.mark.parametrize("effort", ["", "  ", "off", "none", "ultra"])
    def test_invalid_values_ignored(self, effort):
        assert "reasoning_effort" not in _kwargs("deepseek-v4-flash", effort)

    @pytest.mark.parametrize("effort", ["minimal", "low", "medium", "high"])
    def test_valid_values(self, effort):
        assert _kwargs("deepseek-v4-flash", effort)["reasoning_effort"] == effort

    def test_case_and_space_normalized(self):
        assert _kwargs("deepseek-v4-flash", "  HIGH ")["reasoning_effort"] == "high"


class TestUnsupportedDetection:
    """检测器必须要求错误里明确提到推理参数——否则任何被网关吞掉详情的 400
    都会被误判成推理问题，把真实故障掩盖成一次静默降级。"""

    @pytest.mark.parametrize(
        "detail",
        [
            "Unrecognized request argument supplied: reasoning_effort",
            "reasoning_effort is not supported for this model",
            "invalid parameter: reasoning effort",
            "reasoning: unsupported field",
            "extra field `reasoning` not permitted",
        ],
    )
    def test_positive(self, detail):
        assert LLMService._detail_indicates_reasoning_unsupported(detail)

    @pytest.mark.parametrize(
        "detail",
        [
            "",
            "   ",
            "rate limit exceeded",
            "The supported API model names are deepseek-v4-pro or deepseek-v4-flash",
            "response_format json_object must contain the word json",
            "model is thinking about your request",  # 含 reasoning 语义但无否定词
        ],
    )
    def test_negative(self, detail):
        assert not LLMService._detail_indicates_reasoning_unsupported(detail)

    def test_empty_body_not_claimed(self):
        """空错误体是 response_format 降级的信号，推理分支不能抢它。"""
        assert not LLMService._detail_indicates_reasoning_unsupported("")


class _DummySessionFactory:
    """替掉 AsyncSessionLocal：这里只验证取值与缓存语义，不需要真实 DB。"""

    def __call__(self):
        return self

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc_info):
        return False


def _fresh_service(monkeypatch, getter):
    monkeypatch.setattr("app.services.llm_service.AsyncSessionLocal", _DummySessionFactory())
    monkeypatch.setattr(LLMService, "_get_config_value_for_session", getter)
    svc = LLMService(session=None)
    # 类属性缓存跨实例共享，逐个测试必须先清掉，否则相互串味
    LLMService._aux_effort_cache = None
    LLMService._aux_effort_expires_at = 0.0
    return svc


def _const(value):
    async def _getter(self, session, key):
        return value

    return _getter


class TestAuxEffortResolution:
    @pytest.mark.asyncio
    async def test_default_when_unset(self, monkeypatch):
        svc = _fresh_service(monkeypatch, _const(None))
        assert await svc._resolve_aux_reasoning_effort() == "low"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw,expected", [
        ("minimal", "minimal"), ("HIGH", "high"), ("  low ", "low"),
        ("off", None), ("none", None), ("disabled", None),
        ("garbage", "low"),  # 非法值回落默认档而不是关闭降档
    ])
    async def test_values(self, monkeypatch, raw, expected):
        svc = _fresh_service(monkeypatch, _const(raw))
        assert await svc._resolve_aux_reasoning_effort() == expected

    @pytest.mark.asyncio
    async def test_cached_between_calls(self, monkeypatch):
        """每次结构化调用都要读这个值，没有缓存等于给每次调用加一次 DB 往返。"""
        calls = {"n": 0}

        async def _counting(self, session, key):
            calls["n"] += 1
            return "minimal"

        svc = _fresh_service(monkeypatch, _counting)
        assert await svc._resolve_aux_reasoning_effort() == "minimal"
        assert await svc._resolve_aux_reasoning_effort() == "minimal"
        assert calls["n"] == 1

    @pytest.mark.asyncio
    async def test_db_failure_degrades_to_no_downgrade(self, monkeypatch):
        async def _boom(self, session, key):
            raise RuntimeError("db down")

        svc = _fresh_service(monkeypatch, _boom)
        assert await svc._resolve_aux_reasoning_effort() is None
