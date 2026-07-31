"""向量集合维度不匹配守卫回归测试。

历史现象（2026-07-31 实测）：后台「接口管理」把 embedding 模型从 jina-embeddings-v4
(2048 维) 换成 jina-clip-v2 (1024 维) 后，既有 rag_chunks/rag_summaries 仍是建表时的
2048 维 → Qdrant 对每次写入/检索返回 400。而本服务全是 best-effort 调用，异常被吞成
零散 warning，整个向量层静默死亡（一次跑批刷出 31 条）。
ensure_schema 原先只在集合缺失时创建，对已存在的集合从不校验维度。
"""
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.services.vector_store_service import VectorStoreService


def _service(existing_dim):
    svc = VectorStoreService.__new__(VectorStoreService)
    svc._schema_ready = False
    client = AsyncMock()
    client.collection_exists = AsyncMock(return_value=True)  # 集合已存在 → 走校验分支
    client.get_collection = AsyncMock(
        return_value=SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(
                vectors=SimpleNamespace(size=existing_dim)))
        )
    )
    svc._client = client
    return svc


@pytest.mark.asyncio
async def test_dim_mismatch_logs_error(caplog):
    """既有集合维度与当前 embedding 不一致 → 必须留下可检索的 ERROR。"""
    svc = _service(existing_dim=2048)
    svc._resolve_vector_size = AsyncMock(return_value=1024)

    with caplog.at_level(logging.ERROR):
        await svc.ensure_schema()

    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("维度不匹配" in m for m in errors), errors
    assert any("2048" in m and "1024" in m for m in errors), errors


@pytest.mark.asyncio
async def test_matching_dim_is_silent(caplog):
    """维度一致时不得误报。"""
    svc = _service(existing_dim=1024)
    svc._resolve_vector_size = AsyncMock(return_value=1024)

    with caplog.at_level(logging.ERROR):
        await svc.ensure_schema()

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_guard_never_blocks_schema_ready(caplog):
    """校验失败（如 get_collection 抛错）不得影响 schema 就绪。"""
    svc = _service(existing_dim=2048)
    svc._resolve_vector_size = AsyncMock(return_value=1024)
    svc._client.get_collection = AsyncMock(side_effect=RuntimeError("boom"))

    await svc.ensure_schema()

    assert svc._schema_ready is True
