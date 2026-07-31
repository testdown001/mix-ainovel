"""测试 MemoryLayerService AsyncMemory 升级。

验证：
1. 构造不再触发同步 Memory 初始化
2. _ensure_memory() 返回 AsyncMemory 实例
3. get_memory_context 使用 AsyncMemory.search
4. update_memory_after_chapter 使用 AsyncMemory.add
5. build_chapter_state_context 行为不变（纯 DB 操作）
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

# 避免 SQLAlchemy mapper 未初始化导致 KeyError
import app.models.user_quota  # noqa: F401

from app.services.memory_layer_service import MemoryLayerService


def _dummy_session():
    """链式 mock：让 SystemConfigRepository.get_by_key 返回 None（配置回落 env）。

    mem0 通道配置已改走 SystemConfig（原先直读 settings 导致线上用占位 key 恒 401），
    _build_mem0_config 因此会查库；本文件只测 AsyncMemory 升级，不测配置来源。
    """
    session = SimpleNamespace()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))
    )
    return session


def _make_service():
    """构造 MemoryLayerService，不触发任何外部连接。"""
    return MemoryLayerService(
        db=_dummy_session(),
        llm_service=SimpleNamespace(),
        prompt_service=SimpleNamespace(),
    )


def test_init_does_not_create_memory_instance():
    """构造函数不应触发 mem0 初始化。"""
    svc = _make_service()
    assert svc._memory is None


def test_ensure_memory_returns_async_memory():
    """_ensure_memory 应通过 AsyncMemory.from_config 创建实例并缓存。"""
    svc = _make_service()

    mock_instance = AsyncMock()

    async def _run():
        with patch(
            "app.services.memory_layer_service.AsyncMemory.from_config",
            new_callable=AsyncMock,
            return_value=mock_instance,
        ) as mock_from_config:
            mem = await svc._ensure_memory()
            assert mem is mock_instance
            mock_from_config.assert_awaited_once()

            # 第二次调用应返回缓存
            mem2 = await svc._ensure_memory()
            assert mem2 is mock_instance
            assert mock_from_config.await_count == 1  # 没有再次调用

    asyncio.run(_run())


def test_get_memory_context_uses_async_search():
    """get_memory_context 应使用 AsyncMemory.search 而非 asyncio.to_thread。"""
    svc = _make_service()

    # Mock DB
    mock_db = AsyncMock()

    class _EmptyResult:
        def scalars(self):
            return self
        def all(self):
            return []
        def first(self):
            # SystemConfigRepository.get_by_key 用的是 scalars().first()
            # （mem0 通道配置改走 SystemConfig 后会走到这里，无记录即回落 env）
            return None

    # Mock time tracker
    tracker = SimpleNamespace(current_time=None, current_date=None, project_id="p1", chapter_time_map={})

    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 4:
            # time tracker 查询
            result = MagicMock()
            result.scalar_one_or_none.return_value = tracker
            return result
        return _EmptyResult()

    mock_db.execute = AsyncMock(side_effect=_side_effect)
    svc.db = mock_db

    # Mock AsyncMemory
    mock_memory = AsyncMock()
    mock_memory.search = AsyncMock(return_value={
        "results": [{"memory": "角色A获得了神秘卷轴"}]
    })

    async def _run():
        with patch(
            "app.services.memory_layer_service.AsyncMemory.from_config",
            new_callable=AsyncMock,
            return_value=mock_memory,
        ):
            result = await svc.get_memory_context("project-1", 5, ["角色A"])

        mock_memory.search.assert_awaited_once()
        assert "角色A获得了神秘卷轴" in result

    asyncio.run(_run())


def test_update_memory_uses_async_add():
    """update_memory_after_chapter 应使用 AsyncMemory.add 而非 asyncio.to_thread。"""
    svc = _make_service()

    # Mock LLM 提取
    svc.extract_character_states_from_chapter = AsyncMock(return_value=[])
    svc.extract_timeline_events_from_chapter = AsyncMock(return_value=[])
    svc._extract_mem0_facts = AsyncMock(return_value=[
        "角色A在第3章获得了神秘卷轴",
        "角色B的左臂受了重伤",
    ])

    # Mock AsyncMemory
    mock_memory = AsyncMock()
    mock_memory.add = AsyncMock(return_value=None)

    async def _run():
        with patch(
            "app.services.memory_layer_service.AsyncMemory.from_config",
            new_callable=AsyncMock,
            return_value=mock_memory,
        ):
            result = await svc.update_memory_after_chapter(
                project_id="project-1",
                chapter_number=3,
                chapter_content="测试章节内容",
                character_names=["角色A", "角色B"],
                user_id=1,
            )

        mock_memory.add.assert_awaited_once()
        assert result["mem0_memories_added"] == 2

    asyncio.run(_run())


def test_build_chapter_state_context_no_mem0():
    """build_chapter_state_context 是纯 DB 操作，不涉及 mem0。"""
    svc = _make_service()

    # Mock DB
    mock_db = AsyncMock()

    class _EmptyResult:
        def scalars(self):
            return self
        def all(self):
            return []
        def first(self):
            # SystemConfigRepository.get_by_key 用的是 scalars().first()
            # （mem0 通道配置改走 SystemConfig 后会走到这里，无记录即回落 env）
            return None
        def scalar_one_or_none(self):
            return None

    mock_db.execute = AsyncMock(return_value=_EmptyResult())
    svc.db = mock_db

    async def _run():
        # 不 mock _ensure_memory — 如果被调用会报错，正好验证不涉及 mem0
        result = await svc.build_chapter_state_context("project-1", 5)
        assert result is None  # 无数据时返回 None

    asyncio.run(_run())
