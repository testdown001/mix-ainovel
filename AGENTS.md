# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Project Overview

Arboris-Novel is an AI-assisted novel writing platform for long-form fiction workflows. It is a full-stack system with:

- a FastAPI backend for authoring, generation, review, storage, and admin APIs
- a Vue 3 + TypeScript frontend for workspace, writing desk, inspiration mode, and admin operations
- an optional Go gateway layer for production traffic, task dispatch, WebSocket push, proxying, and rate limiting

The main authoring loop is:

concept dialogue -> blueprint generation -> chapter outline -> context planning and retrieval -> AI chapter generation -> review and selection -> memory/vector persistence -> future retrieval

## Source Of Truth

- The current source of truth is the code under `backend/app/`, `frontend/src/`, and `gateway/`.
- Repository-level docs such as `README.md` and some architecture reports are useful context, but parts of them are stale relative to the current runtime code.
- When code and prose docs disagree, trust the runtime code paths.
- In particular, the current backend generation stack is more modular than the simplified descriptions in older docs, and vector retrieval is centered on Qdrant plus optional BM25/hybrid retrieval rather than older libsql-centric wording.

## Repository Shape

Current indexed repository shape at a glance:

- `backend/app/services/`: 113 Python service files
- `backend/app/api/routers/`: 22 router files
- `backend/app/models/`: 25 ORM model files
- `backend/prompts/`: 37 prompt templates
- `backend/tests/`: 56 `test_*.py` files
- `frontend/src/views/`: 11 view files
- `frontend/src/components/`: 81 component files
- `gateway/`: 21 Go source files

Key top-level areas:

- `backend/app/`: backend runtime code
- `backend/prompts/`: Markdown prompt templates synced into DB at startup
- `backend/storage/`: local development storage assets
- `backend/logs/`: application and LLM logs
- `frontend/src/`: frontend application source
- `gateway/`: Go gateway, dispatcher, proxy, WebSocket hub
- `deploy/`: Docker and deployment assets
- `docs/`: design notes, audits, migration and architecture documents

Avoid committing generated artifacts such as `frontend/node_modules/`, local `.env` files, or local storage databases unless explicitly required.

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
pytest tests/test_service_first_regression_matrix.py
pytest tests/test_agent_system_precollected_context.py
pytest -k "test_name"
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

### Gateway Development

```bash
cd gateway
go mod download
go run cmd/gateway/main.go
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

- `app.log`: general application logs
- `llm.log`: LLM API calls and responses

The Go gateway exposes its own logs and Prometheus metrics and can publish task progress over Redis-backed channels.

## Runtime Entry Points

### Backend App Boot

- `backend/app/main.py`: FastAPI app assembly
- startup lifespan:
  - runs `init_db()`
  - preloads prompts through `PromptService.preload()`
- active middleware in the Python app:
  - `RequestIdMiddleware`
  - `RateLimitMiddleware`
  - CORS middleware

### API Router Registration

`backend/app/api/routers/__init__.py` is the backend API aggregation point. The active router groups include:

- auth and quota
- novels and projects
- writer and optimizer
- reference novel library
- LLM config
- foreshadowing and power system
- admin and updates
- analytics and enhanced analytics
- writing preferences and writing templates
- review and skill APIs
- writer progress
- Celery task status APIs
- Go gateway worker adapter

### Frontend Boot

- `frontend/src/main.ts`: app bootstrap, Pinia, router, login token handoff from URL
- `frontend/src/router/index.ts`: route table and auth/admin guards

### Gateway Boot

- `gateway/cmd/gateway/main.go`: Fiber app startup
- gateway startup wires:
  - JWT auth
  - rate limit middleware
  - request logging and recovery
  - reverse proxy
  - task dispatcher
  - Redis-backed WebSocket hub
  - Prometheus metrics

## Backend Architecture

The backend still follows the broad layering pattern:

Routers -> Services -> Repositories -> Models

But the chapter generation path is now split across many service-specialized modules rather than being concentrated only in `PipelineOrchestrator`.

### Core Router Responsibilities

- `backend/app/api/routers/novels.py`: project CRUD, concept dialogue, blueprint generation, reference novel binding/search, concept encyclopedia, scene extraction and sync from chapters
- `backend/app/api/routers/writer.py`: advanced generation, SSE streaming generation, batch generation, finalize/select/evaluate, outline regeneration, prediction generation, book/volume summary rebuilds, RAG rebuild, archive access, diagnostics
- `backend/app/api/routers/admin.py`: statistics, users, prompts, update logs, daily request limit, system configs, password management
- `backend/app/api/routers/tasks.py`: Celery task status/cancel/result
- `backend/app/api/routers/task_worker.py`: internal worker endpoint consumed by the Go dispatcher
- `backend/app/api/routers/writer_progress.py`: chapter progress WebSocket plus REST pause/resume/status

### Current Generation Stack

The current generation runtime is a service-first composition. `PipelineOrchestrator` is still the main coordinator, but most responsibilities are delegated to focused services.

Important generation-stage modules:

- planning and config:
  - `pipeline_config_service.py`
  - `context_planner_service.py`
  - `generation_support_service.py`
  - `mission_builder_service.py`
- context access and retrieval:
  - `context_access_service.py`
  - `chapter_context_service.py`
  - `evidence_router_service.py`
  - `generation_context_resolution_service.py`
  - `enhanced_context_service.py`
  - `history_context_service.py`
- prompt assembly:
  - `generation_prompt_context_service.py`
  - `generation_prompt_stage_service.py`
  - `prompt_assembly_service.py`
  - `prompt_compiler_service.py`
  - `writer_prompt_service.py`
- execution flows:
  - `single_version_generation_service.py`
  - `version_generation_service.py`
  - `fast_generation_flow_service.py`
  - `standard_generation_flow_service.py`
  - `literary_generation_flow_service.py`
  - `standard_post_processing_service.py`
- finalize and follow-up:
  - `generation_finalize_service.py`
  - `generation_background_task_service.py`
  - `generation_analysis_task_service.py`
  - `generation_write_task_service.py`
  - `chapter_post_processor.py`
  - `finalize_service.py`
- observability:
  - `generation_telemetry_service.py`
  - `writer_progress_service.py`

The practical flow is closer to:

1. `PipelineConfigService` resolves preset and feature flags.
2. `ContextPlannerService` builds a `ContextPlan` with retrieval tasks, prompt modules, verification tasks, and token budgets.
3. `EvidenceRouterService` and context services collect plot, arc, state, and symbolic evidence.
4. Prompt context and prompt stage services assemble the final model input.
5. Flow services run one of the fast, standard, or literary execution branches.
6. Review, archive, progress completion, follow-up writes, and stream payload finalization are handled by finalize/background services.

### PipelineOrchestrator

`backend/app/services/pipeline_orchestrator.py` remains the main traditional orchestration entry and is still called by:

- `writer.py`
- Celery tasks
- the Go task-worker adapter
- the Agent bridge

Its current role is to wire and sequence the specialized services, emit telemetry, and return the unified response shape expected by the frontend and Agent bridge.

### Agent System

The project supports two execution modes through `HybridExecutor`:

1. Traditional pipeline via `PipelineOrchestrator`
2. Agent system via `WritingAgentSystem`

Main files:

- `backend/app/agents/hybrid_executor.py`: selects legacy pipeline or Agent path
- `backend/app/agents/system.py`: registers agents and executes the ordered Agent workflow
- `backend/app/agents/base.py`: base Agent contract, stage emission, permissions
- `backend/app/agents/message_bus.py`: in-memory async message bus
- `backend/app/agents/generation_bridge.py`: lets Agent flow reuse pipeline generation/review/consistency capabilities

Current role summary:

- `TaiziAgent`: request triage and goal extraction
- `ZhongshuAgent`: planning hub, context collection, `ContextPlan` and evidence assembly
- `ShangshuAgent`: dispatch and coordination
- `BingbuAgent`: chapter generation
- `HubuAgent`: skill application
- `LibuAgent`: character and consistency checks
- `MenxiaAgent`: review and approval

When changing agents, update both `WritingAgentSystem.AGENT_REGISTRY` and `PERMISSION_MATRIX`.

### Async, Streaming, Tasks, And Progress

Several async delivery mechanisms coexist. Do not confuse them:

- direct SSE generation stream:
  - backend endpoint in `writer.py`
  - frontend consumer in `frontend/src/api/novel.ts`
  - used for `/advanced/generate/stream`
- backend-local chapter progress WebSocket:
  - `backend/app/api/routers/writer_progress.py`
  - powered by `writer_progress_service.py`
- Celery tasks:
  - `backend/app/tasks/chapter_tasks.py`
  - queried through `/api/tasks/*`
- Go dispatcher tasks:
  - frontend `frontend/src/api/task.ts` targets `/tasks`
  - frontend `frontend/src/composables/useWebSocket.ts` connects to gateway `/ws`
  - gateway dispatcher publishes progress via Redis Pub/Sub
  - backend `task_worker.py` acts as the Python worker adapter

### Supporting Backend Subsystems

- retrieval and memory:
  - `vector_store_service.py`
  - `memory_layer_service.py`
  - `chapter_ingest_service.py`
  - `volume_summary_service.py`
  - `book_summary_service.py`
  - `narrative_summary_service.py`
- quality and verification:
  - `gatekeeper_review_service.py`
  - `six_dimension_review_service.py`
  - `narrative_verifier_service.py`
  - `evidence_grader_service.py`
  - `consistency_service.py`
  - `chapter_guardrails.py`
- reference and style:
  - `reference_novel_library_service.py`
  - `web_search_service.py`
  - `reference_prose_service.py`
  - `voice_sample_service.py`
  - `writer_persona_service.py`
  - `user_style_service.py`
  - `fingerprint_service.py`
- system/admin/config:
  - `config_service.py`
  - `admin_setting_service.py`
  - `llm_config_service.py`
  - `cache_service.py`

### Prompts

Prompt templates live in `backend/prompts/` and are loaded into the database at startup. This folder now contains a wider set of prompt assets than older docs implied, including:

- concept and outline prompts
- chapter plan variants
- writing prompt variants
- editor/review/evaluation prompts
- foreshadowing extraction/reminder prompts
- optimization prompts
- reference novel extraction/fusion prompts
- mission and persona prompts

Edit the Markdown prompt files, not DB records.

## Frontend Architecture

Frontend stack: Vue 3 + TypeScript + Naive UI + TailwindCSS 4 + Pinia

### Main Routes

Defined in `frontend/src/router/index.ts`:

- `/`: workspace entry
- `/workspace`: novel workspace
- `/inspiration`: inspiration mode
- `/detail/:id`: novel detail
- `/novel/:id`: writing desk
- `/login`
- `/register`
- `/admin`
- `/admin/novel/:id`
- `/settings`

Route guards enforce:

- authenticated access to workspace routes
- admin-only access to admin routes
- forced password change redirect for admins when required

### Main Views

- `WorkspaceEntry.vue`: entry selector
- `NovelWorkspace.vue`: project list / workspace shell
- `InspirationMode.vue`: concept and inspiration workflow
- `NovelDetail.vue`: project detail shell
- `WritingDesk.vue`: main writing cockpit
- `AdminView.vue`: admin console shell
- `SettingsView.vue`: user-facing settings page

### Writing Desk

`frontend/src/views/WritingDesk.vue` is the main workbench and composes many feature surfaces:

- `WDHeader`
- `WDSidebar`
- `WDWorkspace`
- `WDCodexPanel`
- version/evaluation/edit/outline/batch modals
- `PresetSelector`
- `SkillSelector`
- middle product, diagnostic, and agent visualizer surfaces

This page is the frontend integration point for:

- streaming generation
- chapter prediction
- batch generation
- version selection
- diagnostics
- context plan preview
- RAG rebuilds
- agent and skill configuration

### Admin UI

`frontend/src/views/AdminView.vue` is a tabbed shell that lazy-loads admin modules:

- statistics
- users
- prompts
- novels
- update logs
- system settings
- password/security

`frontend/src/components/admin/SettingsManagement.vue` is the main operational settings page and already supports:

- daily request limit
- polish model config
- reference-search model config
- Agent system toggle
- generic system config CRUD

### Frontend APIs And State

- `frontend/src/api/novel.ts`: largest domain API surface, including concept flow, generation, streaming, prediction, archives, diagnostics, RAG rebuild, scenes, and concept library
- `frontend/src/api/admin.ts`: admin API surface
- `frontend/src/api/task.ts`: Go gateway task-dispatch API surface
- `frontend/src/stores/auth.ts`: auth state, token persistence, auth options
- `frontend/src/stores/novel.ts`: project state
- `frontend/src/composables/useAsyncGeneration.ts`: async task submission and polling/WebSocket fallback
- `frontend/src/composables/useWebSocket.ts`: Go gateway WebSocket client for task progress

## Gateway Architecture

The Go gateway is a production-oriented optional layer in front of FastAPI.

Key responsibilities in current code:

- JWT auth parsing and middleware
- request logging, recovery, and CORS
- token bucket rate limiting and concurrency gating
- reverse proxying to FastAPI
- WebSocket hub with room support
- Redis-backed task event fanout
- task dispatcher with retries, queue priorities, timeouts, and worker pool control
- optional LLM gateway modules with routing, retry, connection pool, and semantic cache

Important files:

- `gateway/cmd/gateway/main.go`
- `gateway/internal/middleware/middleware.go`
- `gateway/internal/ratelimit/limiter.go`
- `gateway/internal/proxy/proxy.go`
- `gateway/internal/websocket/hub.go`
- `gateway/internal/taskdispatcher/dispatcher.go`
- `gateway/internal/taskdispatcher/worker_pool.go`
- `gateway/internal/llmgateway/gateway.go`
- `gateway/internal/llmgateway/router/router.go`
- `gateway/internal/llmgateway/provider/*.go`

Production architecture can be:

Nginx -> Go Gateway -> Python FastAPI workers

## Data, Storage, And Configuration

### Databases And Storage

- MySQL 8.0+ is the default production database
- SQLite is supported for simple local development
- Qdrant is used for vector retrieval and memory-related storage
- BM25 and hybrid retrieval paths exist alongside vector retrieval
- table creation and some schema repair happen at startup through `init_db()` and helper routines rather than formal Alembic-first workflows

### Config Sources

There are multiple config layers:

- environment variables through `backend/app/core/config.py`
- system config KV records through `SystemConfig`
- admin settings through `AdminSetting`
- per-user LLM config through `LLMConfig`

Some runtime behavior is hot-configurable through system configs and admin settings, so before adding new env-only switches, inspect whether the feature should instead be backed by existing config tables.

### Models

The ORM layer includes 25 model files and covers:

- projects, chapters, chapter versions, and chapter outlines
- users and quotas
- prompts and update logs
- constitution, factions, power systems, entity registry
- foreshadowing, memory layers, project memory
- writing archives, writing templates, writer persona
- reference novels and reviews

## Testing Guidance

The repository now has a meaningful focused regression suite rather than only a few isolated tests.

Pay special attention to:

- `backend/tests/test_service_first_regression_matrix.py`
- `backend/tests/test_pipeline_config_service.py`
- `backend/tests/test_context_planner_service.py`
- `backend/tests/test_evidence_router_service.py`
- `backend/tests/test_generation_*`
- `backend/tests/test_standard_generation_flow_service.py`
- `backend/tests/test_literary_generation_flow_service.py`
- `backend/tests/test_agent_system_precollected_context.py`
- `backend/tests/test_writer_quality_updates.py`

Testing approach:

- prefer targeted tests near the changed module
- for generation-path changes, add at least one regression covering the specific broken contract
- do not assume only `PipelineOrchestrator` tests are sufficient; many behaviors now live in specialized services
- if changing task, progress, or stream code, validate both response contracts and event behavior

## Coding Style And Naming Conventions

- Python: 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes
- Keep routers thin; business logic belongs in services
- Prefer async patterns in backend services and DB code
- Frontend Vue SFC components use `PascalCase`
- Frontend TS utilities and composables use `camelCase`
- Frontend formatting follows Prettier with `semi: false`, `singleQuote: true`, `printWidth: 100`
- Backend files may include `# AIMETA` headers used for AI navigation metadata; preserve them
- Route all LLM interactions through `llm_service.py`
- Prefer Naive UI components over ad hoc widgets unless the existing feature already follows a custom local pattern
- Node engine requirement is `^20.19.0 || >=22.12.0`
- Use `logging.getLogger(__name__)` in backend modules

## Troubleshooting Principles

- Fix the root cause, not only the visible symptom
- Trace the full execution chain first:
  - router
  - planning/config
  - retrieval/evidence
  - prompt assembly
  - generation/review
  - persistence/finalization
  - stream/task/progress delivery
- Use production-like evidence before guessing:
  - `backend/logs/app.log`
  - `backend/logs/llm.log`
  - timing data
  - task status
  - stream payloads
  - archive records
- Distinguish symptom guards from root fixes
- Prefer reducing duplicated retrieval, prompt assembly, or LLM work over raising timeouts
- After fixing a bug, add the smallest durable guardrail:
  - regression test
  - clearer logging
  - safer fallback

## Commit And Pull Request Guidelines

- Follow the existing commit style: `feat:`, `fix:`, `docs:`, `refactor:`
- Keep commits small and single-purpose
- Use imperative commit subjects
- Pull requests should include a short summary, impacted areas, validation steps, and screenshots for UI changes
- Call out configuration, schema, gateway, or deployment changes explicitly

## Security And Configuration Tips

- Copy `backend/env.example` or root `.env.example` to `.env` and keep secrets out of git
- Required production secrets include `SECRET_KEY`, `OPENAI_API_KEY`, and `ADMIN_DEFAULT_PASSWORD`
- Common LLM settings include `OPENAI_API_BASE_URL`, `OPENAI_MODEL_NAME`, and `WRITER_CHAPTER_VERSION_COUNT`
- Embedding settings include `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, and `EMBEDDING_BASE_URL`
- Vector settings include `QDRANT_HOST`, `QDRANT_PORT`, `VECTOR_TOP_K_CHUNKS`, `VECTOR_TOP_K_SUMMARIES`, and `VECTOR_CHUNK_SIZE`
- Database settings include `DB_PROVIDER`, `SQLITE_DB_PATH`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`
- Verify `/api/health` after deployment and inspect logs when troubleshooting
