"""finish_reason=length 截断处理回归（LLMResponseTruncated）。

锁定行为边界：
1. 默认 fail_on_truncation=False：finish_reason=length 仍返回半截内容（旧行为完全不变）；
2. fail_on_truncation=True：真实检测点（_stream_and_collect_impl）抛 LLMResponseTruncated，
   partial_text 保留半截内容，且不触发兜底通道重试（截断非通道故障）；
3. 写作路径（single_version）：截断→提升 max_tokens 重试一次；再截断→502 失败；
   与无效正文重试不叠加，全程最多 3 次调用；
4. 场景路径（scene）：截断→提升 max_tokens 重试一次；再截断→保留 partial_text，场景级不整章失败。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import app.models  # noqa: F401  触发 mapper 注册
from app.core.config import settings
from app.services.llm_service import LLMResponseTruncated, LLMService
from app.services.generation_telemetry_service import GenerationTelemetryService
from app.services.scene_generation_service import SceneGenerationService
from app.services.single_version_generation_service import SingleVersionGenerationService

VALID_CHAPTER_BODY = (
    "雨声砸在青瓦上，沈砚推开窗，冷风卷着潮气扑进屋内。"
    "街口的灯笼被风吹得一晃一晃，红光落在他的指节上，像一层迟迟不肯退去的血色。"
    "他听见楼下有人压低声音争吵，茶盏碰在桌沿，发出短促的一声响。"
    "那声音让他想起昨夜未写完的信，也想起信尾被墨水洇开的名字。"
)

_LLM_CONFIG = {
    "api_key": "test-key",
    "base_url": "https://llm.example.com/v1",
    "model": "test-model",
    "api_format": "openai",
    "reasoning_effort": None,
}


class _TruncatingStreamClient:
    """stream_chat 输出半截内容后以 finish_reason=length 收尾。"""

    def __init__(self, text: str = "半截正文，句子断在了中"):
        self.text = text

    async def stream_chat(self, **kwargs):
        yield {"content": self.text}
        yield {"finish_reason": "length"}


def _patched_service(monkeypatch, client) -> LLMService:
    svc = LLMService(session=None)
    monkeypatch.setattr(svc, "_resolve_llm_config", AsyncMock(return_value=dict(_LLM_CONFIG)))
    monkeypatch.setattr(svc, "_get_or_create_client", lambda *a, **k: client)
    monkeypatch.setattr(svc, "_increment_usage_metric", AsyncMock())
    monkeypatch.setattr(svc, "_record_token_usage", AsyncMock())
    monkeypatch.setattr(svc, "_record_call_log", AsyncMock())
    return svc


# ---------- llm_service 层 ----------

@pytest.mark.parametrize("body", ["", " " * 256, "\n\t\u3000"])
def test_blank_body_is_failure_and_uses_fallback(monkeypatch, body):
    class StreamClient:
        calls = 0

        async def stream_chat(self, **kwargs):
            self.calls += 1
            yield {"content": body if self.calls == 1 else '{"ok":true}'}
            yield {"finish_reason": "stop"}

    client = StreamClient()
    svc = _patched_service(monkeypatch, client)
    monkeypatch.setattr(svc, "_resolve_fallback_llm_config", AsyncMock(return_value=dict(_LLM_CONFIG)))
    out = asyncio.run(svc.get_llm_response("system", []))
    assert out == '{"ok":true}'
    calls = svc._record_call_log.await_args_list
    assert calls[0].kwargs["status"] == "error"
    assert "空白正文" in calls[0].kwargs["error_message"]
    assert calls[1].kwargs["api_type"] == "fallback"
    assert calls[1].kwargs["status"] == "success"


def test_blank_body_without_fallback_has_clear_error(monkeypatch):
    svc = _patched_service(monkeypatch, _TruncatingStreamClient("   "))
    monkeypatch.setattr(svc, "_resolve_fallback_llm_config", AsyncMock(return_value=None))
    with pytest.raises(HTTPException, match="空白正文"):
        asyncio.run(svc.get_llm_response("system", []))

def test_default_behavior_returns_partial_content(monkeypatch):
    """fail_on_truncation 缺省 False：截断仍返回半截内容，与旧版一致。"""
    svc = _patched_service(monkeypatch, _TruncatingStreamClient())

    out = asyncio.run(svc.get_llm_response("system", [{"role": "user", "content": "hi"}]))

    assert out == "半截正文，句子断在了中"


def test_llm_call_is_attached_to_active_chapter_telemetry(monkeypatch):
    async def _emit_stream(event, payload=None):
        return None

    telemetry = GenerationTelemetryService(_emit_stream)
    svc = _patched_service(monkeypatch, _TruncatingStreamClient("一段完整正文"))

    out = asyncio.run(svc.get_llm_response("system", [{"role": "user", "content": "hi"}]))

    assert out == "一段完整正文"
    call = telemetry.llm_metrics["calls"][0]
    assert call["status"] == "success"
    assert call["model"] == "test-model"
    assert call["first_token_ms"] is not None
    assert call["prompt_tokens"] > 0
    assert call["completion_tokens"] > 0
    assert call["retry_count"] == 0


def test_fail_on_truncation_raises_and_skips_fallback(monkeypatch):
    """fail_on_truncation=True：检测点抛 LLMResponseTruncated，且不触发兜底通道。"""
    svc = _patched_service(monkeypatch, _TruncatingStreamClient())
    fallback_resolver = AsyncMock(return_value=dict(_LLM_CONFIG))
    monkeypatch.setattr(svc, "_resolve_fallback_llm_config", fallback_resolver)

    with pytest.raises(LLMResponseTruncated) as exc_info:
        asyncio.run(
            svc.get_llm_response(
                "system",
                [{"role": "user", "content": "hi"}],
                fail_on_truncation=True,
            )
        )

    assert exc_info.value.partial_text == "半截正文，句子断在了中"
    # 截断非通道故障：兜底通道解析绝不能被触发
    fallback_resolver.assert_not_awaited()


# ---------- single_version 写作路径 ----------

class _ScriptedLLM:
    """按脚本逐次返回：Exception 则抛出，str 则返回。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def get_llm_response(self, **kwargs):
        self.calls.append(kwargs)
        action = self.script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


class _DummyGuardrails:
    def check(self, **kwargs):
        return SimpleNamespace(passed=True, violations=[])

    def apply_local_patches(self, content, result):
        return content


class _DummyPolicy:
    @staticmethod
    def resolve_temperature(chapter_mission):
        return 0.75


class _DummyCompression:
    async def compress_overlength(self, text, *, target_max, user_id):
        return text[:target_max]

    @staticmethod
    def hard_trim_to_limit(text, limit):
        return text[:limit]


def _single_version_service(llm) -> SingleVersionGenerationService:
    return SingleVersionGenerationService(
        llm_service=llm,
        guardrails=_DummyGuardrails(),
        generation_policy_service=_DummyPolicy(),
        text_compression_service=_DummyCompression(),
        preview_generation_service_factory=lambda: None,
    )


def _run_single_version(service):
    config = SimpleNamespace(preset="fast", enable_preview=False)
    return asyncio.run(
        service.generate(
            index=0,
            prompt_input="prompt",
            writer_prompt="writer",
            style_hint=None,
            project_id="proj-1",
            chapter_number=1,
            outline_title="第一章",
            outline_summary="摘要",
            chapter_mission={"pov": "林玄"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            writer_blueprint={},
            memory_context=None,
            enhanced_context=None,
            config=config,
            target_word_count=3000,
            max_word_count=4000,
            genre_profile=None,
        )
    )


def test_single_version_truncation_retries_with_raised_max_tokens():
    llm = _ScriptedLLM([LLMResponseTruncated("半截……"), VALID_CHAPTER_BODY])
    service = _single_version_service(llm)

    result = _run_single_version(service)

    assert len(llm.calls) == 2
    # 初值按目标 3000 字留 20% tokenizer 余量；截断后仅扩到最大字数的 1.25 倍，
    # 避免一次截断把预算重新放大到会输出 6k~8k 字的旧区间。
    assert llm.calls[0]["max_tokens"] == 3600
    assert llm.calls[1]["max_tokens"] == 5000
    assert llm.calls[0]["fail_on_truncation"] is True
    assert llm.calls[1]["fail_on_truncation"] is True
    assert result["metadata"]["truncation_retry"] == {"max_tokens": 5000}
    assert result["content"] == VALID_CHAPTER_BODY


def test_single_version_double_truncation_fails_with_502():
    llm = _ScriptedLLM([LLMResponseTruncated("半截一"), LLMResponseTruncated("半截二")])
    service = _single_version_service(llm)

    with pytest.raises(HTTPException) as exc_info:
        _run_single_version(service)

    assert exc_info.value.status_code == 502
    assert len(llm.calls) == 2  # 截断重试只重试一次，不再第三次调用


def test_single_version_truncation_and_invalid_retries_cap_at_three_calls():
    """截断重试 + 无效正文重试不叠加成 4 次：全程最多 3 次调用。"""
    invalid_output = (
        "1.  分析任务：\n角色：擅长小说润色的文学编辑。\n目标：提升文字的文学性。\n限制：直接输出正文。\n"
    )
    llm = _ScriptedLLM(
        [LLMResponseTruncated("半截……"), invalid_output, VALID_CHAPTER_BODY]
    )
    service = _single_version_service(llm)

    result = _run_single_version(service)

    assert len(llm.calls) == 3
    assert result["metadata"]["truncation_retry"] == {"max_tokens": 5000}
    assert result["metadata"]["invalid_output_retry"] is True
    # 无效正文重试沿用已提升的 max_tokens，并同样要求截断即失败
    assert llm.calls[2]["max_tokens"] == 5000
    assert llm.calls[2]["fail_on_truncation"] is True
    assert result["content"] == VALID_CHAPTER_BODY


def test_single_version_invalid_retry_truncated_fails_with_502():
    """无效正文重试再截断：直接按失败处理，不再叠加截断重试。"""
    invalid_output = (
        "1.  分析任务：\n角色：擅长小说润色的文学编辑。\n目标：提升文字的文学性。\n限制：直接输出正文。\n"
    )
    llm = _ScriptedLLM([invalid_output, LLMResponseTruncated("半截……")])
    service = _single_version_service(llm)

    with pytest.raises(HTTPException) as exc_info:
        _run_single_version(service)

    assert exc_info.value.status_code == 502
    assert len(llm.calls) == 2


# ---------- scene 场景路径 ----------

_SCENE_MISSION = {
    "pov": "林玄",
    "scene_list": [
        {"goal": "开场", "target_words": 700},
        {"goal": "收尾", "target_words": 700},
    ],
}


def _scene_service(llm) -> SceneGenerationService:
    return SceneGenerationService(
        llm_service=llm,
        guardrails=_DummyGuardrails(),
        generation_policy_service=_DummyPolicy(),
        text_compression_service=_DummyCompression(),
    )


def _run_scene(service):
    return asyncio.run(
        service.generate_scene_by_scene(
            prompt_sections_data={},
            writer_prompt="writer",
            chapter_mission=_SCENE_MISSION,
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
        )
    )


def test_scene_truncation_retries_with_raised_max_tokens():
    llm = _ScriptedLLM(
        [LLMResponseTruncated("场景一残句"), "场景一正文，江面起了雾。", "场景二正文，钟声敲了三下。"]
    )
    service = _scene_service(llm)

    result = _run_scene(service)

    assert len(llm.calls) == 3
    # 场景初值 min(4096, 700*1.8)=1260；重试提升为 min(writer_max_tokens, 1260*1.5)=1890
    assert llm.calls[0]["max_tokens"] == 1260
    assert llm.calls[1]["max_tokens"] == min(settings.writer_max_tokens, 1890)
    # 下一场景恢复自身初值，不继承上一场景的提升
    assert llm.calls[2]["max_tokens"] == 1260
    assert all(call["fail_on_truncation"] is True for call in llm.calls)
    assert "场景一正文" in result["content"]
    assert "场景二正文" in result["content"]
    assert "残句" not in result["content"]


def test_scene_double_truncation_keeps_partial_text():
    """场景重试仍截断：保留 partial_text 继续拼章，不整章失败。"""
    llm = _ScriptedLLM(
        [
            LLMResponseTruncated("场景一残句甲"),
            LLMResponseTruncated("场景一残句乙"),
            "场景二正文，钟声敲了三下。",
        ]
    )
    service = _scene_service(llm)

    result = _run_scene(service)

    assert len(llm.calls) == 3
    # 保留的是重试那次的半截内容
    assert "场景一残句乙" in result["content"]
    assert "场景二正文" in result["content"]
