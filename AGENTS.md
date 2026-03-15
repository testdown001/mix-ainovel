# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Project Overview

Arboris-Novel is an AI-assisted novel writing platform. It is a full-stack application with a FastAPI backend and a Vue 3 frontend. The core workflow is:

concept dialogue -> blueprint generation -> chapter outline -> AI chapter generation with RAG retrieval -> multi-version review -> vectorization for future context

## Project Structure And Module Organization

- `backend/app/`: core backend code, organized as routers -> services -> repositories -> models/schemas.
- `backend/prompts/`: Markdown prompt templates loaded by backend services and synced into the database at startup.
- `backend/storage/`: local SQLite and vector DB files for development.
- `backend/logs/`: application and LLM logs.
- `frontend/src/`: UI source (`views/`, `components/`, `stores/`, `api/`, `router/`, `composables/`).
- `deploy/`: Docker Compose and deployment scripts.
- `docs/`: architecture and audit documentation.
- `gateway/`: Go gateway and dispatcher components used in the production-oriented architecture.

Avoid committing generated artifacts such as `frontend/node_modules/`, local `.env` files, or local storage databases unless the task explicitly requires them.

## Common Commands

### Backend Development

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
uvicorn app.main:app --reload
```

### Backend Testing

```bash
cd backend
source .venv/bin/activate
pytest
pytest tests/test_prompt_service.py
pytest -v
pytest -k "test_name"
pytest app/services/test_phase4_integration.py -q
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
npm run build
npm run build-only
npm run type-check
npm run format
```

### Docker Deployment

```bash
cd deploy
cp ../.env.example .env
docker compose up -d
```

For a SQLite-based local stack:

```bash
DB_PROVIDER=sqlite docker compose up -d
```

Health check endpoint: `GET /api/health`

## Logs

Application logs are written to `backend/logs/`:

- `app.log`: general application logs.
- `llm.log`: LLM API calls and responses.

## Architecture

### Backend

The backend follows a layered architecture:

Routers -> Services -> Repositories -> Models

Key backend areas:

- `backend/app/main.py`: FastAPI entrypoint, lifespan setup, database init, prompt preload, router registration.
- `backend/app/api/routers/`: REST endpoints. Key routers include `writer.py`, `novels.py`, `auth.py`, and `admin.py`.
- `backend/app/services/`: business logic. Important services include:
  - `pipeline_orchestrator.py`: traditional chapter generation pipeline.
  - `llm_service.py`: unified LLM and embedding access layer.
  - `novel_service.py`: novel CRUD and related business logic.
  - `blueprint_service.py`: blueprint and outline management.
  - `chapter_context_service.py`: active RAG retrieval entrypoint.
  - `vector_store_service.py`: vector DB chunk and summary operations.
  - `writer_shared.py`: shared writing helpers and guardrail utilities.
  - `chapter_post_processor.py`: post-selection processing and vector persistence.
  - `finalize_service.py`: memory update and chapter finalization.
  - `writing_archive_service.py`: generation history archive.
- `backend/app/agents/`: agent system implementation based on the san sheng liu bu model.
- `backend/app/models/`: SQLAlchemy ORM models including novel, chapter, character, foreshadowing, memory, writing archive, and configuration entities.
- `backend/app/skills/`: writing skill implementations such as style, dialogue, rhythm, emotion, and consistency helpers.
- `backend/app/schemas/`: Pydantic request and response schemas.
- `backend/app/core/config.py`: settings loader and DB connection assembly.

### Frontend

Frontend stack: Vue 3 + TypeScript + Naive UI + TailwindCSS 4 + Pinia

Key frontend areas:

- `frontend/src/router/index.ts`: route definitions and auth guards.
- `frontend/src/views/`: page-level views such as `WritingDesk.vue`, `InspirationMode.vue`, `NovelWorkspace.vue`, and `AdminView.vue`.
- `frontend/src/components/`: reusable UI components organized by feature.
- `frontend/src/stores/`: Pinia stores for auth and novel state.
- `frontend/src/api/`: API wrappers for backend endpoints.
- `frontend/src/composables/`: shared composition utilities.

Path alias: `@` -> `frontend/src/`

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

### Database

- MySQL 8.0+ is the default production database.
- SQLite is supported for simpler local development with file-backed storage in `storage/`.
- libsql is used for vector storage in `storage/rag_vectors.db`.
- Database access is async.
- Tables are created through startup initialization rather than actively maintained Alembic migrations.

### Agent System

The project supports two execution modes through `HybridExecutor`:

1. Traditional pipeline via `PipelineOrchestrator`
2. Agent system via `WritingAgentSystem`

Agent flow:

Taizi -> Zhongshu -> Shangshu -> Menxia
                    -> Bingbu / Hubu / Libu

Role summary:

- `TaiziAgent`: request triage and writing goal extraction.
- `ZhongshuAgent`: planning hub and task construction.
- `ShangshuAgent`: coordination and dispatch.
- `BingbuAgent`: chapter generation.
- `HubuAgent`: skill application.
- `LibuAgent`: character consistency.
- `MenxiaAgent`: quality review and final approval.

When adding or changing agents, update both `WritingAgentSystem.AGENT_REGISTRY` and `PERMISSION_MATRIX`.

### RAG Pipeline

The active retrieval entrypoint is `ChapterContextService.retrieve_multi_query()`.

Typical flow:

1. Build multiple query strings from outline title, outline summary, writing notes, and character names.
2. Retrieve top chunks and summaries through `VectorStoreService`.
3. Inject retrieved context into the generation prompt alongside blueprint and prior chapter summaries.
4. After finalization, split text, embed it, and store the vectors.
5. Use hybrid retrieval only when `rag_retrieval_mode="hybrid"` is configured.

### Chapter Generation Pipeline

Request -> quota check -> config resolve -> context assembly -> mission generation -> strategy resolve -> generate versions -> optional post-process stages -> quality review -> select best -> async finalize

Many behaviors are gated by boolean flags in `PipelineConfig`.

### Go Gateway

Production-oriented architecture can run as:

Nginx -> Go Gateway -> Python FastAPI workers

Relevant areas:

- `gateway/cmd/gateway/main.go`: API gateway.
- Go gateway responsibilities include JWT handling, rate limiting, WebSocket hub support, reverse proxying, model routing, retries, semantic cache, dispatching, and progress push.
- Python worker adapter: `backend/app/api/routers/task_worker.py`

## Coding Style And Naming Conventions

- Python: 4-space indentation, `snake_case` for functions and modules, `PascalCase` for classes.
- Keep routers thin and place business logic in `backend/app/services/`.
- Prefer async patterns in backend services and DB code.
- Frontend Vue SFC components use `PascalCase`.
- Frontend TS utilities and composables use `camelCase`.
- Frontend formatting follows Prettier with `semi: false`, `singleQuote: true`, and `printWidth: 100`.
- Backend files may include `# AIMETA` headers used for AI navigation metadata; preserve them when editing.
- Route all LLM interactions through `llm_service.py`; do not call OpenAI or Ollama directly from routers.
- Prompt templates live in `backend/prompts/*.md`; edit those files rather than database records.
- Prefer Naive UI components over ad hoc frontend widgets unless the existing code clearly uses a custom pattern.
- TailwindCSS 4 is used for frontend styling.
- Node engine requirement is `^20.19.0 || >=22.12.0`.
- Use `logging.getLogger(__name__)` in backend modules.

## Integrated Advanced Features

These features are implemented and integrated into the generation pipeline:

- `PowerSystem` and `PowerLevel` for power scaling consistency.
- `NovelConstitution` for world-building constraints.
- `BlueprintRelationship` for prompt-time relationship injection.
- `CharacterState` for arc and state continuity.
- `EntityRegistry` and `EntityAlias` for anti-hallucination entity validation.
- `Foreshadowing` for bidirectional extraction and future constraint injection.
- `WritingArchive` for generation history and optimization feedback.
- Analytics such as emotion curve, tension, and character arc signals.
- `ConsistencyService` as both constraint and review layer.

Frontend shells like `MiddleProductViewer`, `DiagnosticPanel`, and `AgentFlowVisualizer` may be present as integrated or work-in-progress surfaces depending on current frontend status.

## Testing Guidelines

- Existing automated coverage is limited.
- The current repository already includes integration-style coverage such as `backend/app/services/test_phase4_integration.py`.
- For backend work, add focused tests close to the changed module and include at least one regression case when practical.
- Prefer targeted validation before broad test runs when working on a narrow area.

## Commit And Pull Request Guidelines

- Follow the existing commit style: `feat:`, `fix:`, `docs:`, `refactor:`. Optional scopes are acceptable.
- Keep commits small and single-purpose.
- Use imperative commit subjects.
- Pull requests should include a short summary, impacted areas, validation steps, and screenshots for UI changes.
- Call out configuration, schema, or deployment changes explicitly.

## Security And Configuration Tips

- Copy `backend/env.example` or root `.env.example` to `.env` and keep secrets out of git.
- Required production secrets include `SECRET_KEY`, `OPENAI_API_KEY`, and `ADMIN_DEFAULT_PASSWORD`.
- Common LLM-related settings include `OPENAI_API_BASE_URL`, `OPENAI_MODEL_NAME`, and `WRITER_CHAPTER_VERSION_COUNT`.
- Embedding-related settings include `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, and `EMBEDDING_BASE_URL`.
- Vector DB settings include `VECTOR_DB_URL`, `VECTOR_TOP_K_CHUNKS`, `VECTOR_TOP_K_SUMMARIES`, and `VECTOR_CHUNK_SIZE`.
- Database settings include `DB_PROVIDER`, `SQLITE_DB_PATH`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`.
- Verify `/api/health` after deployment and inspect `backend/logs/` when troubleshooting.
