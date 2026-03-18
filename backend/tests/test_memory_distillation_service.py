"""MemoryDistillationService 单元测试（8 例）"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.memory_distillation_service import (
    DISTILL_THRESHOLD,
    MemoryDistillationService,
)


# ── helpers ──────────────────────────────────────────────────────────────

def _make_memories(n, prefix="fact"):
    return [{"id": f"mem_{i}", "memory": f"{prefix} {i}: 测试事实内容"} for i in range(n)]


def _mock_llm(*, grader_configured=True, response_json=None, raise_error=False):
    llm = SimpleNamespace()

    if grader_configured:
        if raise_error:
            llm.get_grader_llm_response = AsyncMock(side_effect=RuntimeError("LLM error"))
        else:
            default = response_json or json.dumps({
                "kept": [{"id": "mem_0", "memory": "fact 0: 测试事实内容"}],
                "merged": [{"ids": ["mem_1", "mem_2"], "memory": "合并后的事实"}],
                "obsolete": [{"id": "mem_3", "reason": "被后续事件取代"}],
            })
            llm.get_grader_llm_response = AsyncMock(return_value=default)
    else:
        # 模拟 grader 未配置
        async def _no_grader(*args, **kwargs):
            raise RuntimeError("grader not configured")
        llm.get_grader_llm_response = _no_grader

    return llm


def _mock_memory(memories=None):
    mem = AsyncMock()
    mem.get_all = AsyncMock(return_value={"results": memories or []})
    mem.delete = AsyncMock()
    mem.add = AsyncMock()
    return mem


# ── tests ────────────────────────────────────────────────────────────────

def test_should_distill_below_threshold():
    """<100 条不触发"""
    llm = _mock_llm()
    service = MemoryDistillationService(llm)
    service._memory = _mock_memory(_make_memories(50))

    result = asyncio.run(service.should_distill("proj1"))
    assert result is False


def test_should_distill_above_threshold():
    """>=100 条触发"""
    llm = _mock_llm()
    service = MemoryDistillationService(llm)
    service._memory = _mock_memory(_make_memories(DISTILL_THRESHOLD + 5))

    result = asyncio.run(service.should_distill("proj1"))
    assert result is True


def test_distill_merge_duplicates():
    """重复事实被合并"""
    llm = _mock_llm()
    service = MemoryDistillationService(llm)
    mock_mem = _mock_memory(_make_memories(5))
    service._memory = mock_mem

    result = asyncio.run(service.distill("proj1", user_id=1))

    assert result["status"] == "completed"
    assert result["merged"] == 1
    assert result["obsolete"] == 1
    assert mock_mem.delete.call_count >= 1
    assert mock_mem.add.call_count == 1


def test_distill_obsolete_outdated():
    """过时记忆被淘汰"""
    response = json.dumps({
        "kept": [],
        "merged": [],
        "obsolete": [
            {"id": "mem_0", "reason": "信息过时"},
            {"id": "mem_1", "reason": "被后续覆盖"},
        ],
    })
    llm = _mock_llm(response_json=response)
    service = MemoryDistillationService(llm)
    mock_mem = _mock_memory(_make_memories(3))
    service._memory = mock_mem

    result = asyncio.run(service.distill("proj1", user_id=1))

    assert result["obsolete"] == 2
    assert mock_mem.delete.call_count == 2
    assert mock_mem.add.call_count == 0


def test_distill_dry_run():
    """dry_run 不执行实际删改"""
    llm = _mock_llm()
    service = MemoryDistillationService(llm)
    mock_mem = _mock_memory(_make_memories(5))
    service._memory = mock_mem

    result = asyncio.run(service.distill("proj1", user_id=1, dry_run=True))

    assert result["status"] == "dry_run"
    assert result["merged"] == 1
    assert result["obsolete"] == 1
    mock_mem.delete.assert_not_called()
    mock_mem.add.assert_not_called()


def test_distill_llm_parse_error():
    """LLM 返回非法 JSON 时全量保留"""
    llm = _mock_llm(response_json="这不是JSON{broken")
    service = MemoryDistillationService(llm)
    mock_mem = _mock_memory(_make_memories(3))
    service._memory = mock_mem

    result = asyncio.run(service.distill("proj1", user_id=1))

    assert result["status"] == "completed"
    assert result["merged"] == 0
    assert result["obsolete"] == 0
    mock_mem.delete.assert_not_called()
    mock_mem.add.assert_not_called()


def test_distill_grader_not_configured():
    """grader 未配置时静默跳过"""
    llm = _mock_llm(grader_configured=False)
    service = MemoryDistillationService(llm)
    mock_mem = _mock_memory(_make_memories(5))
    service._memory = mock_mem

    result = asyncio.run(service.distill("proj1", user_id=1))

    assert result["status"] == "completed"
    assert result["kept"] == 5
    assert result["merged"] == 0
    assert result["obsolete"] == 0
    mock_mem.delete.assert_not_called()
    mock_mem.add.assert_not_called()


def test_distill_empty_memories():
    """无记忆时直接返回"""
    llm = _mock_llm()
    service = MemoryDistillationService(llm)
    service._memory = _mock_memory([])

    result = asyncio.run(service.distill("proj1", user_id=1))

    assert result["status"] == "skipped"
    assert result["reason"] == "empty"
    assert result["before"] == 0
