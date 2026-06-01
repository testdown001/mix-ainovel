# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Arboris-Novel is an AI-assisted novel writing platform. Full-stack app with a FastAPI (Python 3.11) backend and Vue 3 (TypeScript) frontend. The core workflow: concept dialogue → blueprint generation → chapter outline → AI chapter generation with RAG retrieval → multi-version review → vectorization for future context.

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
- `api/routers/` — REST endpoints. Key routers: `writer.py` (chapter generation, 49KB), `novels.py` (project management), `auth.py` (JWT auth), `admin.py` (admin panel)
- `services/` — 70+ service files. Core services used in chapter generation:
  - `pipeline_orchestrator.py` (46KB) — traditional pipeline orchestrator: context assembly → RAG retrieval → LLM generation → review
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
- `agents/` — Agent system (三省六部 architecture):
  - `system.py` — `WritingAgentSystem` entry point, agent registry and message bus
  - `hybrid_executor.py` — `HybridExecutor` switches between traditional pipeline and agent system based on config
  - `base.py` — `BaseAgent` abstract class with message handling
  - `message_bus.py` — async message bus for inter-agent communication
  - Individual agents (5, converged 2026-06-01): `taizi_agent.py` (需求分拣), `zhongshu_agent.py` (规划中枢), `bingbu_agent.py` (章节生成), `hubu_agent.py` (技能系统), `menxia_agent.py` (质量审核). **Note**: `shangshu_agent.py`(调度) and `libu_agent.py`(角色) were never invoked by the main loop and have been deleted; the message bus is no longer used for routing.
- `models/` — SQLAlchemy ORM models (25 tables): Novel, Chapter, ChapterVersion, Character, Faction, Constitution, Foreshadowing (5 tables), MemoryLayer, CharacterState, PowerSystem/Level, WritingArchive, WriterPersona, LLMConfig, EntityRegistry, etc.
- `skills/` — Writing skill implementations: `platinum_style.py`, `dialogue_polish.py`, `rhythm_control.py`, `foreshadowing.py`, `emotion_boost.py`, `consistency_check.py`
- `schemas/` — Pydantic request/response schemas
- `core/config.py` — `Settings` class (pydantic-settings), loads from `.env`. Key property: `sqlalchemy_database_uri` auto-builds connection string based on `DB_PROVIDER`
- `prompts/` — 22 Markdown prompt templates (concept, writing, evaluation, extraction, etc.), loaded into DB at startup by `PromptService.preload()`

### Frontend (`frontend/src/`)

Vue 3 + TypeScript + Naive UI + TailwindCSS 4 + Pinia

- `router/index.ts` — route definitions with auth guards (`requiresAuth`, `requiresAdmin` meta)
- `views/` — page components. Core: `WritingDesk.vue` (main writing interface, 25KB), `InspirationMode.vue`, `NovelWorkspace.vue`, `AdminView.vue`
- `components/` — 26+ reusable components organized by feature (`writing-desk/`, `novel-detail/`, `admin/`, `shared/`)
- `stores/` — Pinia stores for auth and novel state
- `api/` — API client wrappers for backend endpoints
- `composables/` — Vue 3 composition functions
- Path alias: `@` → `frontend/src/`
- Vite dev server proxies `/api` to `http://127.0.0.1:8000`

### Database

- **MySQL 8.0+** (default): production-ready, async via `asyncmy`
- **SQLite**: zero config alternative, file at `storage/arboris.db` (set `DB_PROVIDER=sqlite`)
- **Qdrant** (optional): vector DB for RAG, stores `rag_chunks` (text embeddings) and `rag_summaries` (chapter summary embeddings); also used by Mem0 for long-term memory
- All DB access is async (aiosqlite / asyncmy). Session factory: `db/session.py` → `AsyncSessionLocal` (SQLite connections enable `PRAGMA foreign_keys=ON`)
- Tables are bootstrapped via `init_db()` `create_all` at startup. An **Alembic** scaffold now exists (`backend/alembic.ini` + `backend/migrations/`, async env) as the versioned-migration path going forward; the first baseline migration is still pending.
- PK type `BIGINT_PK_TYPE` uses `BigInteger().with_variant(Integer, "sqlite")` so autoincrement works on the SQLite dev backend.

### Agent System (三省六部)

The project supports two execution modes via `HybridExecutor`:

1. **Traditional Pipeline** (`PipelineOrchestrator`) — **the only real generation engine** and the default path.
2. **Agent System** (`WritingAgentSystem`) — opt-in. **Reality check (2026-06-01)**: the agent path is a thin sequential wrapper, NOT an independent engine — 兵部(Bingbu) calls back into the same `PipelineOrchestrator` via `generation_bridge.py`. It has been converged to a 3-stage sequential flow (Planner → Writer → Reviewer); `PERMISSION_MATRIX` and message-bus routing are removed. Per GitHub/arXiv research (Re3→DOC→DOME; ACL'24/'26 multi-agent critiques), the "拟人官僚多 Agent" metaphor yields no proven quality gain over pipeline; treat pipeline as the canonical path.

Converged agent flow (sequential, return-value driven — no inter-agent messaging):
```
太子省 (Taizi, 规划) → 户部 (Hubu, 可选技能) → 中书省 (Zhongshu, 规划)
  → 兵部 (Bingbu, 生成 → 回调 PipelineOrchestrator) → 门下省 (Menxia, 审查)
```

- **太子省 (TaiziAgent)**: Request triage, extracts writing goals from user input
- **中书省 (ZhongshuAgent)**: Planning hub, assembles context and constructs writing tasks
- **兵部 (BingbuAgent)**: Chapter generation (delegates to `PipelineOrchestrator`)
- **户部 (HubuAgent)**: Skill system, applies writing techniques and style templates
- **门下省 (MenxiaAgent)**: Quality review, final approval gate

Toggle between modes: set `use_agent_system` in chapter generation request or via system config.

### RAG Pipeline

Active entry point: `ChapterContextService.retrieve_multi_query()`. The second retrieval implementation `KnowledgeRetrievalService` (the old `rag_mode=two_stage` path) has been **removed** (2026-06-01); `rag_mode=two_stage` is still accepted as input but now gracefully falls back to the single `simple` vector-RAG path. The Agentic evidence budget/grading (`evidence_router._enforce_evidence_budgets`) is **telemetry/diagnostic only** — it does NOT feed the generation prompt.

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

Key: 37 boolean config flags in `PipelineConfig` control feature toggling per preset (basic/enhanced/literary/creative/agent)

### Go Gateway (Phase 2)

Production architecture: Nginx → Go Gateway → Python FastAPI Workers
- `gateway/cmd/gateway/main.go` — **the single production entry** (JWT, rate limit, WebSocket Hub, reverse proxy). Forwards gateway-verified identity to FastAPI via `X-Gateway-*` headers (client-supplied copies are stripped).
- Go Task Dispatcher: priority queue, concurrency control, worker pool, progress push via Redis Pub/Sub
- Python worker adapter: `backend/app/api/routers/task_worker.py`
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
- Logging: use `logging.getLogger(__name__)` in backend modules; logs auto-route to `backend/logs/app.log` or `llm.log`
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
