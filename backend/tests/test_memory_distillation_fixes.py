"""mem0 蒸馏双 bug 回归：from_config 须 await + 命名空间与写入侧一致（user_id=project_id）。

修复前：
1. `AsyncMemory.from_config(config)` 漏 await → self._memory 是 coroutine，
   任何方法调用 AttributeError 被 except 吞掉，should_distill 恒 False。
2. 蒸馏侧用 `novel_{project_id}` 命名空间，而写入/检索侧
   （memory_layer_service）用 project_id → 蒸馏永远查到空集。
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.services.llm_service import LLMService
from app.services.memory_distillation_service import (
    DISTILL_THRESHOLD,
    MemoryDistillationService,
)


# ── helpers ──────────────────────────────────────────────────────────────

def _make_memories(n):
    return [{"id": f"mem_{i}", "memory": f"fact {i}: 测试事实内容"} for i in range(n)]


def _mock_llm(response_json=None):
    llm = LLMService.__new__(LLMService)
    default = response_json or json.dumps({
        "kept": [{"id": "mem_0", "memory": "fact 0: 测试事实内容"}],
        "merged": [{"ids": ["mem_1", "mem_2"], "memory": "合并后的事实"}],
        "obsolete": [{"id": "mem_3", "reason": "被后续事件取代"}],
    })
    llm.get_grader_llm_response = AsyncMock(return_value=default)
    # 蒸馏侧构建 mem0 配置时要借 llm_service 的 session（配置已改走 SystemConfig）
    llm.session = None
    return llm


def _mock_memory(memories):
    mem = AsyncMock()
    mem.get_all = AsyncMock(return_value={"results": memories})
    mem.delete = AsyncMock()
    mem.add = AsyncMock()
    return mem


# ── tests ────────────────────────────────────────────────────────────────

def test_ensure_memory_awaits_from_config():
    """_ensure_memory 必须 await from_config(config_dict=...)，拿到实例而非 coroutine。"""
    service = MemoryDistillationService(_mock_llm())
    mem_instance = _mock_memory([])
    fake_cls = MagicMock()
    fake_cls.from_config = AsyncMock(return_value=mem_instance)

    with patch("mem0.AsyncMemory", fake_cls), patch(
        "app.services.memory_layer_service.MemoryLayerService._build_mem0_config",
        new=AsyncMock(return_value={"cfg": 1}),
    ):
        memory = asyncio.run(service._ensure_memory())

    assert memory is mem_instance
    fake_cls.from_config.assert_awaited_once_with(config_dict={"cfg": 1})


def test_should_distill_true_through_real_ensure_memory():
    """超阈值时 should_distill 走完整 _ensure_memory 路径返回 True，且检索命名空间为 project_id。"""
    service = MemoryDistillationService(_mock_llm())
    mem_instance = _mock_memory(_make_memories(DISTILL_THRESHOLD + 5))
    fake_cls = MagicMock()
    fake_cls.from_config = AsyncMock(return_value=mem_instance)

    with patch("mem0.AsyncMemory", fake_cls), patch(
        "app.services.memory_layer_service.MemoryLayerService._build_mem0_config",
        new=AsyncMock(return_value={"cfg": 1}),
    ):
        result = asyncio.run(service.should_distill("proj-1"))

    assert result is True
    # 命名空间必须与 memory_layer_service 写入侧一致（user_id=project_id）
    assert mem_instance.get_all.await_args.kwargs["user_id"] == "proj-1"


def test_distill_uses_project_id_namespace():
    """distill 的 get_all/add 都用 user_id=project_id（而非 novel_ 前缀）。"""
    service = MemoryDistillationService(_mock_llm())
    mock_mem = _mock_memory(_make_memories(5))
    service._memory = mock_mem

    result = asyncio.run(service.distill("proj-1", user_id=1))

    assert result["status"] == "completed"
    assert mock_mem.get_all.await_args.kwargs["user_id"] == "proj-1"
    mock_mem.add.assert_awaited_once()
    assert mock_mem.add.await_args.kwargs["user_id"] == "proj-1"
