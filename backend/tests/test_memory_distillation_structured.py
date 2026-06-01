"""memory_distillation 接入 generate_structured（grader 通道，responder 适配）后的行为锁定。"""
import asyncio

from app.services.llm_service import LLMService
from app.services.memory_distillation_service import MemoryDistillationService


def _make_service(grader_responses):
    llm = LLMService.__new__(LLMService)  # 跳过 __init__
    queue = list(grader_responses)

    async def _fake_grader(*args, **kwargs):
        return queue.pop(0)

    llm.get_grader_llm_response = _fake_grader  # type: ignore[attr-defined]
    return MemoryDistillationService(llm)


def test_distill_batch_valid_grader_json():
    svc = _make_service([
        '{"kept":["m1"],"merged":[{"ids":["m2","m3"],"memory":"合并后"}],"obsolete":[{"id":"m4"}]}'
    ])
    out = asyncio.run(svc._distill_batch([{"id": "m1", "memory": "a"}], user_id=1))
    assert out["kept"] == ["m1"]
    assert out["merged"][0]["ids"] == ["m2", "m3"]
    assert out["obsolete"][0]["id"] == "m4"


def test_distill_batch_garbage_falls_back_to_full_retention():
    memories = [{"id": "m1", "memory": "a"}, {"id": "m2", "memory": "b"}]
    svc = _make_service(["不是JSON", "还是垃圾"])
    out = asyncio.run(svc._distill_batch(memories, user_id=1))
    # default=DistillBatchResult(kept=memories) → 全量保留，不丢记忆
    assert out["kept"] == memories
    assert out["merged"] == []
    assert out["obsolete"] == []
