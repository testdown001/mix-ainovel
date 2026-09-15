import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.generation_quality_gate import (
    GenerationQualityError,
    GenerationQualityGate,
    assert_selectable,
    content_digest,
)
from app.services.scene_generation_service import SceneContract
from app.utils.llm_capabilities import strict_response_format, supports_sampling


TEXT = ("夜雨敲在窗上。林玄收起信，推门走进巷子。身后的灯随即熄灭，他停了一瞬，仍向前走去。"
        "巷尾传来脚步，他没有回头，只把信纸攥得更紧。远处的城门缓缓合拢，风里带着潮湿的铁锈味。")


class _LLM:
    async def generate_structured(self, **kwargs):
        from app.services.generation_quality_gate import NarrativeCheck
        return NarrativeCheck(issues=[], state_delta=["林玄收起信并走进巷子"])


def test_quality_gate_verifies_and_records_hash():
    gate = GenerationQualityGate(_LLM())
    report = asyncio.run(gate.check(text=TEXT, context={"mission": "进入巷子"}, user_id=1))
    assert report["status"] == "verified"
    assert report["content_hash"] == content_digest(TEXT)
    assert report["state_delta"]


def test_missing_scene_is_blocking_and_selection_rejects():
    gate = GenerationQualityGate(_LLM())
    with pytest.raises(GenerationQualityError):
        asyncio.run(gate.verify_versions([
            {"content": TEXT, "metadata": {"missing_scenes": [2]}},
        ], context={}, user_id=1))
    with pytest.raises(HTTPException):
        assert_selectable(TEXT, {"missing_scenes": [2]})
    with pytest.raises(HTTPException):
        assert_selectable(TEXT, {"quality_gate": {"status": "verified", "content_hash": "old"}})


def test_rewrite_failure_keeps_original():
    gate = GenerationQualityGate(_LLM())
    result, report = asyncio.run(gate.accept_rewrite(TEXT, "太短", user_id=1, context={}))
    assert result == TEXT
    assert report["rolled_back"] is True


def test_strict_schema_closes_typed_objects_and_rejects_open_maps():
    typed = SceneContract.model_json_schema()
    native = strict_response_format(typed, "SceneContract")
    assert native["type"] == "json_schema"
    assert native["json_schema"]["strict"] is True
    assert native["json_schema"]["schema"]["additionalProperties"] is False
    assert strict_response_format({"type": "object", "properties": {"x": {"type": "string"}},
                                  "additionalProperties": {"type": "string"}}, "Open") is None


def test_sampling_is_removed_for_current_reasoning_models():
    assert supports_sampling("gpt-6-astra", "medium") is False
    assert supports_sampling("gpt-5.5", "medium") is False
    assert supports_sampling("gpt-4o", None) is True
