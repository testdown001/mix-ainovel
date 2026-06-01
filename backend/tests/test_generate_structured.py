"""LLMService.generate_structured 单测（借鉴 Pydantic AI 结构化输出范式）。

覆盖：首答即合法 / 首答非法→纠正重答合法 / 全部非法且无 default 抛错 /
全部非法但有 default 返回 default / 带 Markdown 代码块的脏输出可被修复。
仅在内存中替换 LLMService.generate 出口，不触达 DB / 网络。
"""
import asyncio
from typing import List

from pydantic import BaseModel

from app.services.llm_service import LLMService, StructuredOutputError


class _Mission(BaseModel):
    summary: str
    beats: List[str]
    tension: int


def _make_service(responses: List[str]) -> LLMService:
    svc = LLMService.__new__(LLMService)  # 跳过 __init__（无需 DB）
    queue = list(responses)

    async def _fake_generate(*args, **kwargs):
        return queue.pop(0)

    svc.generate = _fake_generate  # type: ignore[attr-defined]
    return svc


def test_valid_first_try():
    svc = _make_service(['{"summary":"开篇","beats":["相遇","冲突"],"tension":7}'])
    out = asyncio.run(svc.generate_structured(prompt="写大纲", schema=_Mission))
    assert isinstance(out, _Mission)
    assert out.summary == "开篇"
    assert out.beats == ["相遇", "冲突"]
    assert out.tension == 7


def test_repairs_markdown_fenced_json():
    raw = "```json\n{\"summary\":\"x\",\"beats\":[],\"tension\":3}\n```"
    svc = _make_service([raw])
    out = asyncio.run(svc.generate_structured(prompt="p", schema=_Mission))
    assert out.tension == 3


def test_invalid_then_valid_retry():
    # 首答缺字段(tension) → 校验失败 → 第二答合法
    svc = _make_service([
        '{"summary":"缺字段","beats":[]}',
        '{"summary":"修正后","beats":["a"],"tension":5}',
    ])
    out = asyncio.run(svc.generate_structured(prompt="p", schema=_Mission, max_validation_retries=1))
    assert out.summary == "修正后"
    assert out.tension == 5


def test_all_invalid_raises():
    svc = _make_service(['not json', '{"still":"bad"}'])
    try:
        asyncio.run(svc.generate_structured(prompt="p", schema=_Mission, max_validation_retries=1))
        assert False, "应抛 StructuredOutputError"
    except StructuredOutputError as e:
        assert e.schema_name == "_Mission"


def test_all_invalid_returns_default():
    fallback = _Mission(summary="默认", beats=[], tension=0)
    svc = _make_service(['garbage', 'still garbage'])
    out = asyncio.run(
        svc.generate_structured(
            prompt="p", schema=_Mission, max_validation_retries=1, default=fallback
        )
    )
    assert out is fallback
