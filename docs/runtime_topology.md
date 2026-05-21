# Runtime topology

The current production shape should keep FastAPI as the source of truth for novel and chapter-generation domain behavior.

## Minimal stack

```text
Browser -> reverse proxy/container app -> FastAPI -> MySQL/SQLite
                                             -> Qdrant
                                             -> LLM provider
```

Use this stack for simple deployments and local validation. It matches `deploy/docker-compose.yml`, which starts the application container and Qdrant while expecting MySQL to be provided externally.

## Full async stack

```text
Browser -> Nginx/Go Gateway -> FastAPI domain APIs -> MySQL
                            -> Redis -> Celery workers / task status / progress fanout
                            -> Qdrant -> RAG and memory retrieval
                            -> LLM provider
```

In this mode the Gateway should stay at the API edge: authentication handoff, rate limiting, WebSocket fanout, task dispatch, payment/quota edge flows, metrics, and reverse proxying. Chapter-generation business rules, context planning, prompt assembly, review, archival, and finalization should remain in FastAPI services.

## Boundary rules

- Do not duplicate chapter-generation domain logic in the Gateway. Gateway generation endpoints should delegate to FastAPI worker/domain APIs.
- Both legacy pipeline generation and Agent generation must return the shared generation result contract: `project_id`, `chapter_number`, `preset`, `best_version_index`, `variants`, `review_summaries`, and optional `debug_metadata`.
- Schema changes should be promoted to explicit migrations. Startup schema repair is a compatibility fallback, not the primary migration mechanism.
