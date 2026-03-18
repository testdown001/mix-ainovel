import asyncio

from app.utils import rerank_utils as module


def test_resolve_rerank_config_prefers_dedicated_reranker_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "rag_reranker_api_url", "https://router.example/v1/rerank")
    monkeypatch.setattr(module.settings, "rag_reranker_api_key", "rerank-key")
    monkeypatch.setattr(module.settings, "rag_reranker_model", "jina-reranker-v3")

    async def _unexpected(_: str):
        raise AssertionError("embedding fallback should not be used when dedicated reranker config is set")

    monkeypatch.setattr(module, "_get_embedding_config", _unexpected)

    api_url, api_key, model = asyncio.run(module._resolve_rerank_config())

    assert api_url == "https://router.example/v1/rerank"
    assert api_key == "rerank-key"
    assert model == "jina-reranker-v3"


def test_resolve_rerank_config_falls_back_to_embedding_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "rag_reranker_api_url", None)
    monkeypatch.setattr(module.settings, "rag_reranker_api_key", None)
    monkeypatch.setattr(module.settings, "rag_reranker_model", "jina-reranker-v3")

    async def _fake_embedding_config(key: str):
        values = {
            "embedding.base_url": "https://router.example/v1",
            "embedding.api_key": "embedding-key",
        }
        return values.get(key)

    monkeypatch.setattr(module, "_get_embedding_config", _fake_embedding_config)

    api_url, api_key, model = asyncio.run(module._resolve_rerank_config())

    assert api_url == "https://router.example/v1/rerank"
    assert api_key == "embedding-key"
    assert model == "jina-reranker-v3"


def test_get_rerank_runtime_status_marks_chapter_generation_integration_source(monkeypatch):
    monkeypatch.setattr(module.settings, "rag_reranker_enabled", True)
    monkeypatch.setattr(module.settings, "rag_reranker_api_url", "https://router.example/v1")
    monkeypatch.setattr(module.settings, "rag_reranker_api_key", "rerank-key")
    monkeypatch.setattr(module.settings, "rag_reranker_model", "jina-reranker-v3")

    status = asyncio.run(module.get_rerank_runtime_status())

    assert status == {
        "enabled": True,
        "model": "jina-reranker-v3",
        "config_source": "dedicated",
        "api_url": "https://router.example/v1/rerank",
        "api_key_configured": True,
    }
