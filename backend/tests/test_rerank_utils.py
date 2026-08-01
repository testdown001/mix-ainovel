"""Reranker 地址/密钥解析（env 兜底路径）。

配置源优先级与后台测试入口在 test_rerank_config_source.py；本文件只覆盖
「SystemConfig 里没有 rerank.* 记录」时纯 env 兜底的行为——即老部署升级后、
管理员还没进后台改过任何东西的那一刻，解析结果必须和改造前完全一致。
"""
import asyncio
from contextlib import asynccontextmanager

import pytest

from app.utils import rerank_utils as module


@pytest.fixture
def empty_system_config(monkeypatch):
    """把 SystemConfig 表桩成空，强制走 env 兜底（避免测试真连库）。"""

    class _Rows:
        def all(self):
            return []

    class _Session:
        async def execute(self, *_a, **_k):
            return _Rows()

    @asynccontextmanager
    async def _factory():
        yield _Session()

    import app.db.session as db_session

    monkeypatch.setattr(db_session, "AsyncSessionLocal", _factory)


def test_resolve_rerank_config_prefers_dedicated_reranker_settings(monkeypatch, empty_system_config):
    """专用 reranker 配置齐全时，绝不去借 embedding 配置。"""
    monkeypatch.setattr(module.settings, "rag_reranker_api_url", "https://router.example/v1/rerank")
    monkeypatch.setattr(module.settings, "rag_reranker_api_key", "rerank-key")
    monkeypatch.setattr(module.settings, "rag_reranker_model", "jina-reranker-v3")
    # embedding 也配着，但不该被选中
    monkeypatch.setattr(module.settings, "embedding_base_url", "https://embedding.example/v1")
    monkeypatch.setattr(module.settings, "embedding_api_key", "embedding-key")

    api_url, api_key, model = asyncio.run(module._resolve_rerank_config())

    assert api_url == "https://router.example/v1/rerank"
    assert api_key == "rerank-key"
    assert model == "jina-reranker-v3"


def test_resolve_rerank_config_falls_back_to_embedding_settings(monkeypatch, empty_system_config):
    monkeypatch.setattr(module.settings, "rag_reranker_api_url", None)
    monkeypatch.setattr(module.settings, "rag_reranker_api_key", None)
    monkeypatch.setattr(module.settings, "rag_reranker_model", "jina-reranker-v3")
    monkeypatch.setattr(module.settings, "embedding_base_url", "https://router.example/v1")
    monkeypatch.setattr(module.settings, "embedding_api_key", "embedding-key")

    api_url, api_key, model = asyncio.run(module._resolve_rerank_config())

    assert api_url == "https://router.example/v1/rerank"
    assert api_key == "embedding-key"
    assert model == "jina-reranker-v3"


def test_get_rerank_runtime_status_marks_chapter_generation_integration_source(
    monkeypatch, empty_system_config
):
    monkeypatch.setattr(module.settings, "rag_reranker_enabled", True)
    # 专用地址原样使用，不再被补 /rerank
    monkeypatch.setattr(module.settings, "rag_reranker_api_url", "https://router.example/v1/rerank/multimodal")
    monkeypatch.setattr(module.settings, "rag_reranker_api_key", "rerank-key")
    monkeypatch.setattr(module.settings, "rag_reranker_model", "jina-reranker-v3")

    status = asyncio.run(module.get_rerank_runtime_status())

    assert status == {
        "enabled": True,
        "model": "jina-reranker-v3",
        "config_source": "dedicated",
        "api_url": "https://router.example/v1/rerank/multimodal",
        "api_key_configured": True,
    }
