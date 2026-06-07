# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Arboris-Novel is an AI-assisted long-form fiction writing platform. It combines a FastAPI (Python 3.11) backend, a Vue 3 + TypeScript frontend, and an optional Go gateway for production traffic, WebSocket progress, reverse proxying, and task dispatch. The core workflow is: concept dialogue → blueprint generation → chapter outline → context planning and retrieval → AI chapter generation → review/selection → memory and vector persistence for future context.

## Common Commands

### Backend Development
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # then edit .env with real values
uvicorn app.main:app --reload  # starts on http://127.0.0.1:8000
```

### Testing
```bash
cd backend
source .venv/bin/activate
pytest                           # run all tests
pytest tests/test_prompt_service.py  # run specific test file
pytest -v                        # verbose output
pytest -k "test_name"            # run tests matching pattern
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev          # dev server with HMR, proxies /api to backend:8000
npm run build        # type-check + production build
npm run build-only   # skip type-check, just vite build
npm run type-check   # vue-tsc type checking only
npm run format       # prettier formatting on src/
```

### Docker Deployment
```bash
# MySQL (default)
cd deploy && cp ../.env.example .env  # edit .env
docker compose up -d

# SQLite (simpler, for development)
DB_PROVIDER=sqlite docker compose up -d
```

Health check: `GET /api/health`

### Logs
Application logs are written to `backend/logs/`:
- `app.log` — general application logs (10MB rotation, 5 backups)
- `llm.log` — LLM API calls and responses (20MB rotation, 10 backups)
- `trace.log` — lightweight per-stage generation spans as JSON lines (logger `arboris.trace`); grep by `trace_id` to reconstruct one chapter generation's stage timeline (span / duration_ms / seq / status). Emitted via `app/utils/tracing.py` + `GenerationTelemetryService.mark_stage`.

## Architecture

### Backend (`backend/app/`)

Layered architecture: **Routers → Services → Repositories → Models**

- `main.py` — FastAPI entry, lifespan (DB init + prompt preload), CORS, router registration
- `api/routers/` — 24 router files. Key routers: `writer.py` (advanced generation, SSE, batch generation, finalize/select/evaluate, outline/prediction, summaries, RAG rebuild, archives, diagnostics), `novels.py` (project/concept/reference workflows), `auth.py` (JWT auth), `admin.py` (admin panel), `task_worker.py` (Go dispatcher worker adapter), `tasks.py` (Celery status/cancel/result)
- `services/` — 110+ service modules. Core services used in chapter generation:
  - `pipeline_orchestrator.py` — traditional pipeline orchestrator: config → context/evidence → prompt assembly → generation flow → finalize/archive/telemetry
  - `pipeline_config_service.py` — resolves `fast` / `standard` / `premium` presets, global settings, and request overrides
  - `context_planner_service.py` — builds `ContextPlan` retrieval, prompt, verification, and token-budget tasks
  - `evidence_router_service.py` — routes local plot, global arc, state, and symbolic evidence and enforces evidence budgets
  - `generation_context_resolution_service.py`, `generation_evidence_stage_service.py`, `generation_prompt_context_service.py`, `generation_prompt_stage_service.py` — generation-stage context and prompt assembly helpers
  - `fast_generation_flow_service.py`, `standard_generation_flow_service.py`, `literary_generation_flow_service.py` — preset-specific execution branches
  - `single_version_generation_service.py`, `version_generation_service.py`, `standard_post_processing_service.py`, `generation_finalize_service.py`, `generation_background_task_service.py` — generation, post-processing, and follow-up writes
  - `llm_service.py` — unified LLM calling (OpenAI-compatible + Ollama), embedding generation
  - `novel_service.py` — novel CRUD and business logic
  - `blueprint_service.py` — chapter outline/blueprint management
  - `chapter_context_service.py` — **active** RAG retrieval entry point (multi-query retrieval)
  - `vector_store_service.py` — Qdrant vector DB operations (chunk/summary storage and retrieval)
  - `writer_shared.py` — shared utilities (mission generation, guardrail rewriting)
  - `chapter_post_processor.py` — post-selection processing (summary + vector storage)
  - `finalize_service.py` — chapter finalization (memory layer, snapshots)
  - `writing_archive_service.py` — 奏折 archive system (generation history)
  - Conditional pipeline services: `humanization_service.py`, `prose_sculptor_service.py`, `consistency_service.py`, `foreshadowing_service.py`, `enrichment_service.py`, `pacing_controller.py`
- `agents/` — Agent system (custom advanced multi-Agent architecture):
  - `system.py` — `WritingAgentSystem` entry point, agent registry, and ordered sequential workflow
  - `hybrid_executor.py` — `HybridExecutor` switches between traditional pipeline and agent system based on config
  - `base.py` — `BaseAgent` abstract class with stage emission, archive hooks, and capability registration
  - `message.py` — Agent data contracts (`AgentContext`, `AgentResult`, `AgentMessage`, capabilities); there is no active `message_bus.py`
  - `generation_bridge.py` — lets `BingbuAgent` reuse `PipelineOrchestrator`
  - `agentic_loop.py` / `context_manager.py` / `agents/tools/` — optional tool-use loop support when `use_agentic_loop` is enabled
  - Individual agents (5, converged 2026-06-01): `taizi_agent.py` (需求分拣), `hubu_agent.py` (技能系统), `zhongshu_agent.py` (规划中枢), `bingbu_agent.py` (章节生成), `menxia_agent.py` (质量审核). **Note**: `shangshu_agent.py` and `libu_agent.py` are not present; routing is return-value driven, not message-bus driven.
- `models/` — SQLAlchemy ORM model files covering projects, conversations, blueprints, chapters, versions, reviews, users/quotas, payments/plans, prompts/config, memory layers, chapter blueprints, constitution, factions, power systems, entity registry, foreshadowing, reference novels, archives, templates, writer persona, usage metrics, and update logs
- `skills/` — Writing skill implementations: `platinum_style.py`, `dialogue_polish.py`, `rhythm_control.py`, `foreshadowing.py`, `emotion_boost.py`, `consistency_check.py`
- `schemas/` — Pydantic request/response schemas
- `core/config.py` — `Settings` class (pydantic-settings), loads from `.env`. Key property: `sqlalchemy_database_uri` auto-builds connection string based on `DB_PROVIDER`
- `prompts/` — 37 Markdown prompt templates (concept, outline, chapter plan, writing variants, editor/review/evaluation, foreshadowing, optimization, reference extraction/fusion, mission/persona, etc.), loaded into DB at startup by `PromptService.preload()`

### Frontend (`frontend/src/`)

Vue 3 + TypeScript + Naive UI + TailwindCSS 4 + Pinia

- `router/index.ts` — route definitions with auth guards (`requiresAuth`, `requiresAdmin` meta)
- `views/` — 16 page components. Core: `WorkspaceEntry.vue`, `NovelWorkspace.vue`, `InspirationMode.vue`, `NovelDetail.vue`, `WritingDesk.vue`, `AdminView.vue`, `AdminNovelDetail.vue`, `SettingsView.vue`, auth/legal/pricing pages
- `components/` — 70+ Vue components organized by feature (`writing-desk/`, `novel-detail/`, `admin/`, `shared/`, plus top-level project/blueprint/reference/persona components)
- `stores/` — Pinia stores for auth and novel state
- `api/` — API client wrappers for backend, gateway task, payment, plan, skill, writing preference/template, update, and review endpoints
- `composables/` — Vue 3 composition functions, including async generation (`useAsyncGeneration.ts`) and gateway WebSocket progress (`useWebSocket.ts`)
- Path alias: `@` → `frontend/src/`
- Vite dev server proxies `/api` to `http://127.0.0.1:8000`

### Database

- **MySQL 8.0+** (default): production-ready, async via `asyncmy`
- **SQLite**: zero config alternative, file at `storage/arboris.db` (set `DB_PROVIDER=sqlite`)
- **Qdrant** (optional): vector DB for RAG, stores `rag_chunks` (text embeddings) and `rag_summaries` (chapter summary embeddings); also used by Mem0 for long-term memory
- All DB access is async (aiosqlite / asyncmy). Session factory: `db/session.py` → `AsyncSessionLocal` (SQLite connections enable `PRAGMA foreign_keys=ON`)
- Tables are bootstrapped via `init_db()` `create_all` plus startup repair helpers. A migration scaffold exists under `backend/migrations/` with baseline revision `3d0894d473c4_baseline_schema.py`; there is currently no `backend/alembic.ini` in the indexed tree, so startup bootstrap/repair remains the local source of truth unless migration config is restored.
- PK type `BIGINT_PK_TYPE` uses `BigInteger().with_variant(Integer, "sqlite")` so autoincrement works on the SQLite dev backend.

### Agent System (Custom Advanced Multi-Agent)

The project supports two execution modes via `HybridExecutor`:

1. **Traditional Pipeline** (`PipelineOrchestrator`) — default service-first generation path.
2. **Agent System** (`WritingAgentSystem`) — opt-in sequential wrapper. `Taizi` parses, optional `Hubu` injects skills, `Zhongshu` plans/contextualizes, `Bingbu` generates through `generation_bridge.py` and `PipelineOrchestrator` by default, and `Menxia` reviews. `PERMISSION_MATRIX` and message-bus routing have been removed.

Converged agent flow (sequential, return-value driven — no inter-agent messaging):
```
需求解析 (Taizi) → 技能增强 (Hubu, optional) → 上下文规划 (Zhongshu)
  → 章节生成 (Bingbu → PipelineOrchestrator) → 质量审核 (Menxia)
```

- **TaiziAgent**: Request triage, extracts writing goals from user input
- **ZhongshuAgent**: Planning hub, assembles context and constructs writing tasks
- **BingbuAgent**: Chapter generation (delegates to `PipelineOrchestrator`)
- **HubuAgent**: Skill system, applies writing techniques and style templates
- **MenxiaAgent**: Quality review, final approval gate

Toggle between modes: set `use_agent_system` in chapter generation request or via system config.

### RAG Pipeline

Active access layer: `ContextAccessService` + `ChapterContextService`. Single-query retrieval uses `retrieve_for_generation()`; evidence/tool paths use `retrieve_multi_query()`. The old `KnowledgeRetrievalService` / `rag_mode=two_stage` implementation is removed from the indexed code. `rag_retrieval_mode` controls vector vs hybrid retrieval, and `EvidenceRouterService` produces evidence packs, budget reports, summaries, and telemetry used by downstream generation stages.

Chapter generation retrieves context from the vector store:
1. Build multiple query strings from outline_title, outline_summary, writing_notes, character names
2. `ChapterContextService` → `VectorStoreService` → vector similarity search: top-K chunks (default 5) + top-K summaries (default 3)
3. Retrieved content injected into LLM prompt alongside blueprint + previous chapter summaries
4. After chapter finalization: text split (LangChain `RecursiveCharacterTextSplitter`, 480 chars/120 overlap) → embed → store in Qdrant
5. Optional hybrid mode: `HybridRetrievalService` (Vector + BM25 + RRF fusion), activated only when `rag_retrieval_mode="hybrid"`

### Chapter Generation Pipeline (Traditional)

```
Request → QuotaCheck → ConfigResolve → ContextAssembly(parallel) → MissionGeneration → StrategyResolve
  → GenerateVersions(×N) → [ProseSculpt] → [Humanize] → [Enrich] → QualityReview → SelectBest
  → AsyncFinalize(MemoryUpdate + VectorStore + Archive)
```

Key: `PipelineConfigService` resolves three active presets (`fast`, `standard`, `premium`) through preset defaults, global settings, and request-level allowlisted overrides. Legacy names such as `basic`, `enhanced`, `ultimate`, `platinum`, and `literary` are accepted only as compatibility aliases.

### Go Gateway (Phase 2)

Production architecture: Nginx → Go Gateway → Python FastAPI Workers
- `gateway/cmd/gateway/main.go` — **the single production entry** (JWT, rate limit, WebSocket Hub, reverse proxy). Forwards gateway-verified identity to FastAPI via `X-Gateway-*` headers (client-supplied copies are stripped).
- Go Task Dispatcher: `/tasks/submit`, `/tasks/:id/status`, `/tasks/:id/cancel`, `/tasks/user/:user_id`, `/tasks/stats`, concurrency control, worker pool, progress push via Redis Pub/Sub
- Python worker adapter: `backend/app/api/routers/task_worker.py`; gateway worker progress callback: `/internal/tasks/:id/progress`
- **Removed (2026-06-01)**: `internal/llmgateway` (no entry, dead) and the entire `cmd/api` dual-binary subgraph (`internal/{service,handler,repository,models,cache,lock,mq}`) — it duplicated FastAPI domain logic in Go. FastAPI is the canonical domain layer.

### Key Env Variables

Required: `SECRET_KEY`, `OPENAI_API_KEY`, `ADMIN_DEFAULT_PASSWORD`

LLM config: `OPENAI_API_BASE_URL`, `OPENAI_MODEL_NAME`, `WRITER_CHAPTER_VERSION_COUNT`

Embedding: `EMBEDDING_PROVIDER` (openai|ollama), `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`

Vector DB: `QDRANT_HOST`, `QDRANT_PORT`, `VECTOR_TOP_K_CHUNKS`, `VECTOR_TOP_K_SUMMARIES`, `VECTOR_CHUNK_SIZE`

DB: `DB_PROVIDER` (sqlite|mysql), `SQLITE_DB_PATH`, `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`

## Code Conventions

- Backend uses `# AIMETA` comment headers on key files for AI navigation metadata (format: `P=purpose|R=responsibility|E=entry_point|...`)
- All backend services are async; use `async/await` throughout
- LLM interactions go through `llm_service.py` — never call OpenAI/Ollama directly from routers
- Prompt templates live in `backend/prompts/*.md` and are synced to DB on startup; edit the `.md` files, not DB records directly
- Frontend uses Naive UI component library — prefer its components over custom implementations
- Frontend styling: TailwindCSS 4 utility classes (PostCSS integration, not `@tailwind` directives)
- Node engine requirement: `^20.19.0 || >=22.12.0`
- Logging: use `logging.getLogger(__name__)` in backend modules; logs route to `backend/logs/app.log`, `llm.log`, or `trace.log` depending on logger configuration
- When adding new agents: register in `WritingAgentSystem._register_agents()` (the `PERMISSION_MATRIX`/message-bus routing has been removed; the flow is sequential and return-value driven)

## Integrated Advanced Features

The following advanced features are fully implemented and **integrated** into the AI chapter generation pipeline:

- **PowerSystem/PowerLevel**: Actively queried and enforced during generation to ensure power scaling consistency.
- **NovelConstitution**: Applied as fundamental world-building constraints during generation.
- **BlueprintRelationship**: Character and entity relationship data is injected into generation prompts for accurate interactions.
- **CharacterState**: Actively queried before generation to ensure character arc and state consistency.
- **EntityRegistry/EntityAlias**: Serves as anti-hallucination data; actively used for name validation and entity disambiguation throughout generation.
- **Foreshadowing**: Full bidirectional flow; extractions feed into future chapter constraints automatically across presets.
- **WritingArchive (奏折)**: Records full generation history and feeds back into the optimization and review processes.
- **Analytics (emotion curve, tension, character arcs)**: Analytical results influence the pacing and flow of subsequent chapters.
- **ConsistencyService**: Actively applied as a generation constraint and review mechanism to maintain strict narrative consistency.
- Frontend shells: `MiddleProductViewer`, `DiagnosticPanel`, `AgentFlowVisualizer` (WIP or integrated based on actual frontend status).
