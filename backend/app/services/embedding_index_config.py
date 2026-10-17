"""Embedding-space identity without API credentials or extra embedding probes."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ..core.config import settings


def _public_base_url(value: Any, provider: str) -> str:
    raw = str(value or ("http://localhost:11434" if provider == "ollama" else "https://api.openai.com/v1")).rstrip("/")
    parsed = urlsplit(raw)
    host = parsed.hostname or ""
    if parsed.port:
        host += f":{parsed.port}"
    # Userinfo/query strings may contain credentials. Neither enters collection names.
    return urlunsplit((parsed.scheme.lower(), host.lower(), parsed.path.rstrip("/"), "", ""))


async def resolve_embedding_identity(llm_service: Any = None, *, user_id: int | None = None) -> dict:
    if llm_service is None:
        from ..db.session import AsyncSessionLocal
        from .llm_service import LLMService
        async with AsyncSessionLocal() as session:
            return await resolve_embedding_identity(LLMService(session), user_id=user_id)
    getter = getattr(llm_service, "_get_config_value", None)
    if getter is None:
        # Pure test/service adapters without the production config resolver.
        provider = settings.embedding_provider or "openai"
        return {"provider": provider, "configured_dimension": settings.embedding_model_vector_size,
                "model": settings.ollama_embedding_model if provider == "ollama" else settings.embedding_model,
                "base_url": _public_base_url(settings.ollama_embedding_base_url or settings.embedding_base_url
                              if provider == "ollama" else settings.embedding_base_url or settings.openai_api_base_url, provider)}
    provider = await getter("embedding.provider") or "openai"
    if provider == "ollama":
        model = await getter("ollama.embedding_model") or "nomic-embed-text:latest"
        base = await getter("ollama.embedding_base_url") or await getter("embedding.base_url")
    else:
        model = await getter("embedding.model") or "text-embedding-3-large"
        base = await getter("embedding.base_url")
        if not base:
            config = await llm_service._resolve_llm_config(user_id)
            base = config.get("base_url")
    configured = await getter("embedding.model_vector_size")
    return {"provider": provider, "model": model, "base_url": _public_base_url(base, provider),
            "configured_dimension": int(configured) if configured else None}


def embedding_fingerprint(identity: dict, dimension: int) -> str:
    if not isinstance(dimension, int) or dimension < 1:
        raise ValueError("embedding_dimension_unknown")
    data = {key: identity.get(key) for key in ("provider", "model", "base_url")}
    data['dimension'] = dimension
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


def revision_embedding_matches(revision: str | None, identity: dict, dimension: int | None = None) -> bool:
    try:
        fingerprint, old_dimension, nonce = (revision or "").split(":")
        old_dimension = int(old_dimension)
        if dimension is not None and old_dimension != dimension:
            return False
        return len(nonce) == 32 and fingerprint == embedding_fingerprint(identity, old_dimension)
    except (ValueError, TypeError):
        return False
