# AGENTS.md

This file provides guidance to coding agents working in this repository.

## Project Overview

Arboris-Novel is an AI-assisted novel writing platform for long-form fiction workflows. It is a full-stack system with:

- a FastAPI backend for authoring, generation, review, storage, and admin APIs
- a Vue 3 + TypeScript frontend for workspace, writing desk, inspiration mode, and admin operations
- an optional Go gateway layer for production traffic, task dispatch, WebSocket push, proxying, and rate limiting

The main authoring loop is:

concept dialogue -> blueprint generation -> chapter outline -> context planning and retrieval -> AI chapter generation -> review and selection -> memory/vector persistence -> future retrieval

Recent git history shows the product surface has moved beyond pure generation into monetization, configurable auth, LLM operations, and inspiration-mode productization. Current work should account for:

- membership tiers (`free`, `creator`, `flagship`) driven by `Plan.tier` and the feature capability registry in `backend/app/core/feature_gating.py`
- configurable login methods: password, Linux.do, WeChat OAuth, Google OAuth, and phone verification-code login
- payment operations through Alipay, WeChat Pay, and Stripe, with Stripe membership activation gated on `payment_status == "paid"`
- admin LLM operations: real connection tests, API usage records, thinking-model compatibility, `reasoning_effort`, real usage tokens, and OpenAI `max_completion_tokens` fallback
- inspiration mode upgrades: muse personas, cross-domain material discovery, inspiration spark injection, and N-way concept divergence with tier gates
- generation robustness upgrades: typed `GenerationState` / `pre_collected_context`, lightweight span tracing, and shared LLM JSON parsing utilities
- structured LLM output through `LLMService.generate_structured()` with Pydantic schema validation and retry-on-validation-error
- scene planning, scene-by-scene literary generation, claim-level narrative verification, and lightweight NovelBench regression snapshots
- security hardening: stricter CORS, security response headers, production HTTPS redirect, request body size limiting, gateway worker auth, and payment idempotency
- architecture cleanup: removed Go `cmd/api`, removed `gateway/internal/llmgateway`, removed Agent message bus routing, removed stale `KnowledgeRetrievalService` / `chapter_tasks.py`; later dead-code batches also removed `core/writing_presets.py`, the `knowledge_context` / `rag_global` two-stage retrieval remnants, the `style_hint` dict `temp_offset` branch, and the unused pipeline-review revise/self-critique/reader-simulation helpers (combined revision and background stage-B analysis replaced them)
- test/CI direction: backend regression coverage expanded, frontend Vitest introduced, and gateway build/deploy paths narrowed to the single gateway binary

## Source Of Truth

- The current source of truth is the code under `backend/app/`, `frontend/src/`, and `gateway/`.
- Repository-level docs such as `README.md` and some architecture reports are useful context, but parts of them are stale relative to the current runtime code.
- When code and prose docs disagree, trust the runtime code paths.
- In particular, the current backend generation stack is more modular than the simplified descriptions in older docs, and vector retrieval is centered on Qdrant plus optional BM25/hybrid retrieval rather than older libsql-centric wording.

## Repository Shape

Current indexed repository shape at a glance:

- `backend/app/services/`: 119 Python service files
- `backend/app/api/routers/`: 24 router files
- `backend/app/models/`: 27 ORM model files
- `backend/prompts/`: 37 prompt templates
- `backend/tests/`: 78 `test_*.py` files
- `frontend/src/views/`: 16 view files
- `frontend/src/components/`: 77 component files
- `gateway/`: 22 Go source files

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
npm run test:unit
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
- `trace.log`: lightweight span traces for generation and service timing

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
  - `RequestSizeLimitMiddleware` with a 10 MB body cap
  - `SecurityHeadersMiddleware`
  - production-only `HTTPSRedirectMiddleware` when `settings.debug` is false
  - CORS middleware

### API Router Registration

`backend/app/api/routers/__init__.py` is the backend API aggregation point. The active router groups include:

- auth, quota, plans, feature gates, payment, and API usage
- novels and projects
- writer and optimizer
- reference novel library
- foreshadowing and power system
- admin and updates
- analytics and enhanced analytics
- writing preferences and writing templates
- review and skill APIs
- writer progress
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
- `backend/app/api/routers/auth.py`: password/JWT auth, auth options, WeChat OAuth, Google OAuth, phone verification-code login
- `backend/app/api/routers/admin.py`: statistics, users, prompts, update logs, daily request limit, system configs, login method configs, password management
- `backend/app/api/routers/plans.py`: membership plan CRUD, `Plan.tier`, capability registry exposure, tier capability display
- `backend/app/api/routers/payment.py`: Alipay/WeChat/Stripe orders, payment callbacks/webhooks, payment records, subscription status derived from quota
- `backend/app/api/routers/api_usage.py`: API/LLM usage records and admin usage reporting
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
  - `generation_state.py`
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
  - `scene_generation_service.py`
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
  - `backend/app/utils/tracing.py`

The practical flow is closer to:

1. `PipelineConfigService` resolves preset and feature flags.
2. `GenerationState` carries typed pre-collected context between stages.
3. `ContextPlannerService` builds a `ContextPlan` with retrieval tasks, prompt modules, verification tasks, and token budgets.
4. `EvidenceRouterService` and context services collect plot, arc, state, and symbolic evidence.
5. Prompt context and prompt stage services assemble the final model input.
6. Flow services run one of the fast, standard, or literary execution branches.
7. Review, archive, progress completion, follow-up writes, and stream payload finalization are handled by finalize/background services.
8. `generation_telemetry_service.py` and `utils/tracing.py` emit timings and spans for diagnostics.

### PipelineOrchestrator

`backend/app/services/pipeline_orchestrator.py` remains the main traditional orchestration entry and is still called by:

- `writer.py`
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
- `backend/app/agents/base.py`: base Agent contract, stage emission, archive hooks, and capability registration
- `backend/app/agents/message.py`: Agent data contracts (`AgentContext`, `AgentResult`, `AgentMessage`, capabilities)
- `backend/app/agents/generation_bridge.py`: lets Agent flow reuse pipeline generation/review/consistency capabilities
- `backend/app/agents/agentic_loop.py` and `backend/app/agents/tools/`: optional tool-use loop support when enabled

Current role summary:

- `TaiziAgent`: request triage and goal extraction
- `HubuAgent`: skill application
- `ZhongshuAgent`: planning hub, context collection, `ContextPlan` and evidence assembly
- `BingbuAgent`: chapter generation
- `MenxiaAgent`: review and approval

When changing agents, update `WritingAgentSystem.AGENT_REGISTRY` / `_register_agents()` and keep the sequential flow in `execute_chapter_generation()` consistent. `PERMISSION_MATRIX` and message-bus routing have been removed.

### Async, Streaming, Tasks, And Progress

Several async delivery mechanisms coexist. Do not confuse them:

- direct SSE generation stream:
  - backend endpoint in `writer.py`
  - frontend consumer in `frontend/src/api/novel.ts`
  - used for `/advanced/generate/stream`
- backend-local chapter progress WebSocket:
  - `backend/app/api/routers/writer_progress.py`
  - powered by `writer_progress_service.py`
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
  - `narrative_claim_service.py`
  - `novel_bench_service.py`
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
- inspiration and muse workflows:
  - `inspiration_spark.py`
  - `muse_material_service.py`
  - `muse_persona.py`
  - `concept_divergence_service.py`
- monetization, auth, and usage:
  - `payment_service.py`
  - `quota_service.py`
  - `usage_service.py`
  - `api_usage_recorder.py`
  - `sms_service.py`
  - `backend/app/core/feature_gating.py`
- LLM operations:
  - `llm_service.py`
  - `backend/app/utils/llm_tool.py`
  - `backend/app/utils/json_utils.py`
  - `LLMService.generate_structured()` for schema-validated Pydantic output
- system/admin/config:
  - `config_service.py`
  - `admin_setting_service.py`
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

- `/`: public landing page
- `/home`: workspace entry
- `/workspace`: novel workspace
- `/inspiration`: inspiration mode
- `/detail/:id`: novel detail
- `/novel/:id`: writing desk
- `/login`
- `/register`
- `/forgot-password`
- `/admin`
- `/admin/novel/:id`
- `/settings`
- `/pricing`
- `/terms`
- `/privacy`

Route guards enforce:

- authenticated access to workspace routes
- admin-only access to admin routes
- forced password change redirect for admins when required
- OAuth/login callback token handoff through URL token parameters in frontend boot/auth store

### Main Views

- `LandingView.vue`: public entry/marketing page
- `WorkspaceEntry.vue`: entry selector
- `NovelWorkspace.vue`: project list / workspace shell
- `InspirationMode.vue`: concept and inspiration workflow, including muse personas, cross-domain material search, inspiration spark injection, concept divergence, and tier-gated controls
- `NovelDetail.vue`: project detail shell
- `WritingDesk.vue`: main writing cockpit
- `AdminView.vue`: admin console shell
- `SettingsView.vue`: user-facing settings page
- `PricingView.vue`: public membership pricing and tier capability display
- `Login.vue`, `Register.vue`, `ForgotPassword.vue`: auth screens

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
- login/auth method configuration
- API management and real connection testing
- password/security
- membership plans
- payment channels
- payment records

`frontend/src/components/admin/SettingsManagement.vue` is the main operational settings page and already supports:

- daily request limit
- polish model config
- reference-search model config
- Agent system toggle
- generic system config CRUD

Admin monetization and operations surfaces include:

- `LoginAuthConfig.vue`: toggles registration, Linux.do, WeChat, Google, phone login, and captcha-related auth options
- `ApiManagement.vue`: default/polish/search/grader LLM configuration, real connection tests, API usage reporting, and reasoning-model settings
- `MembershipPlans.vue`: plan CRUD, `tier` selection, and capability display from the backend registry
- `PaymentChannels.vue`: payment channel configuration, including Stripe support
- `PaymentRecords.vue`: payment order records pulled from the real payment API

### Frontend APIs And State

- `frontend/src/api/novel.ts`: largest domain API surface, including concept flow, generation, streaming, prediction, archives, diagnostics, RAG rebuild, scenes, and concept library
- `frontend/src/api/admin.ts`: admin API surface
- `frontend/src/api/plans.ts`: membership plan and tier capability APIs
- `frontend/src/api/payment.ts`: payment plans, orders, channels, records, and subscription status
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

The current Go side is intentionally a single gateway binary. Old Go business API code under `cmd/api`, duplicate Go domain services/repositories/models, and `internal/llmgateway` have been removed; business APIs and LLM orchestration live in Python FastAPI.

Important files:

- `gateway/cmd/gateway/main.go`
- `gateway/internal/middleware/middleware.go`
- `gateway/internal/ratelimit/limiter.go`
- `gateway/internal/proxy/proxy.go`
- `gateway/internal/websocket/hub.go`
- `gateway/internal/taskdispatcher/dispatcher.go`
- `gateway/internal/taskdispatcher/worker_pool.go`

Production architecture can be:

Nginx -> Go Gateway -> Python FastAPI workers

## Data, Storage, And Configuration

### Databases And Storage

- MySQL 8.0+ is the default production database
- SQLite is supported for simple local development
- Qdrant is used for vector retrieval and memory-related storage
- BM25 and hybrid retrieval paths exist alongside vector retrieval
- table creation and some schema repair happen at startup through `init_db()` and helper routines
- Alembic is configured: `backend/alembic.ini` + `backend/migrations/` with baseline `3d0894d473c4_baseline_schema.py`; startup `init_db()` bootstrap/repair still runs, Alembic is the versioned-migration path going forward

### Config Sources

There are multiple config layers:

- environment variables through `backend/app/core/config.py`
- system config KV records through `SystemConfig`
- admin settings through `AdminSetting`
- plan/tier records through `Plan` and runtime feature gates through `backend/app/core/feature_gating.py`
- payment orders through `PaymentOrder`
- API usage records through `ApiUsageLog`

Some runtime behavior is hot-configurable through system configs and admin settings, so before adding new env-only switches, inspect whether the feature should instead be backed by existing config tables.

Recent LLM/admin settings are stored through system config keys rather than the removed `llm_config.py` router/service. When adding model config, check `llm_service.py`, `admin.py`, `ApiManagement.vue`, and `backend/app/db/system_config_defaults.py`.

Membership feature gates should use the capability registry in `feature_gating.py`; do not duplicate tier checks in frontend-only logic.

### Models

The ORM layer includes 27 model files and covers:

- projects, chapters, chapter versions, and chapter outlines
- users, phone login, quotas, plans, payment orders, and API usage logs
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
- `backend/tests/test_generation_state.py`
- `backend/tests/test_generate_structured.py`
- `backend/tests/test_self_critique_structured.py`
- `backend/tests/test_memory_distillation_structured.py`
- `backend/tests/test_tracing.py`
- `backend/tests/test_parse_llm_json.py`
- `backend/tests/test_thinking_model_compat.py`
- `backend/tests/test_api_usage_recorder.py`
- `backend/tests/test_auth_login_methods.py`
- `backend/tests/test_payment_stripe.py`
- `backend/tests/test_muse_premium_features.py`
- `backend/tests/test_inspiration_spark.py`
- `backend/tests/test_muse_material_service.py`
- `backend/tests/test_user_tier_integration.py`
- `backend/tests/test_pipeline_orchestrator_e2e.py`
- `backend/tests/test_scene_plan_integration.py`
- `backend/tests/test_narrative_claim_service.py`
- `backend/tests/test_task_worker.py`

Testing approach:

- prefer targeted tests near the changed module
- for generation-path changes, add at least one regression covering the specific broken contract
- do not assume only `PipelineOrchestrator` tests are sufficient; many behaviors now live in specialized services
- if changing task, progress, or stream code, validate both response contracts and event behavior
- if changing scene planning, literary mode, or claim verification, cover `scene_generation_service.py`, `narrative_claim_service.py`, and related context-plan tests
- if changing LLM/provider behavior, cover thinking-model compatibility, `reasoning_effort`, usage accounting, and fallback behavior
- if changing structured LLM outputs, prefer `generate_structured()` and cover schema validation/retry behavior
- if changing auth/payment/plans, cover backend contracts and the corresponding frontend API shape; Stripe webhook activation must remain gated on confirmed paid status
- if changing inspiration-mode tier gates, cover both backend feature gates and frontend UI/API expectations
- frontend unit tests use Vitest; run `npm run test:unit` for touched frontend utility/component tests where applicable

## Coding Style And Naming Conventions

- Python: 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes
- Keep routers thin; business logic belongs in services
- Prefer async patterns in backend services and DB code
- Frontend Vue SFC components use `PascalCase`
- Frontend TS utilities and composables use `camelCase`
- Frontend formatting follows Prettier with `semi: false`, `singleQuote: true`, `printWidth: 100`
- Backend files may include `# AIMETA` headers used for AI navigation metadata; preserve them
- Route all LLM interactions through `llm_service.py`
- Prefer `LLMService.generate_structured()` for new schema-shaped LLM outputs instead of hand-parsing loosely shaped JSON.
- Use `backend/app/utils/json_utils.py` helpers such as `parse_llm_json`/repair helpers for LLM JSON parsing; avoid brace-slicing or ad hoc extraction.
- Use `backend/app/utils/tracing.py` spans for meaningful generation-path timing rather than adding one-off timing logs.
- For OpenAI/Claude thinking models, preserve provider-specific handling in `llm_service.py`: `reasoning_effort`, `thinking_budget`, `disable_thinking`, real usage tokens, and `max_completion_tokens` fallback.
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
  - `backend/logs/trace.log`
  - timing data
  - API usage records
  - task status
  - stream payloads
  - archive records
- For membership or feature availability issues, trace `Plan.tier` -> `feature_gating.py` capability registry -> quota-derived subscription state -> frontend gate rendering.
- For login issues, check `auth.py`, `auth_service.py`, `sms_service.py`, `LoginAuthConfig.vue`, and system config keys for enabled login methods.
- For payment issues, trace `payment.py` -> `payment_service.py` -> `PaymentOrder` -> quota activation; do not assume unpaid Stripe sessions should activate membership.
- For generation consistency issues, include scene plan, compiled prompt, retrieved evidence, claim verification output, and review summaries in the investigation before changing prompt text.
- For gateway task issues, check gateway dispatcher/worker pool state, `/tasks/*` response contracts, Redis progress publication, and `task_worker.py` auth/callback behavior.
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
- Runtime LLM/admin model settings may also come from `SystemConfig` keys such as `llm.*`, `llm_optimize.*`, `llm_grader.*`, and `llm_search.*`, including `reasoning_effort`
- Security settings include `CORS_ORIGINS`, `DEBUG=false` for production HTTPS redirects, rate limits, and request-size limits from `main.py` middleware wiring
- Embedding settings include `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, and `EMBEDDING_BASE_URL`
- Vector settings include `QDRANT_HOST`, `QDRANT_PORT`, `VECTOR_TOP_K_CHUNKS`, `VECTOR_TOP_K_SUMMARIES`, and `VECTOR_CHUNK_SIZE`
- Database settings include `DB_PROVIDER`, `SQLITE_PATH`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE`
- Auth method, OAuth, SMS, payment channel, and membership behavior is largely configured through `SystemConfig`, `AdminSetting`, `Plan`, and admin UI records; inspect existing config tables before adding new environment-only switches
- Verify `/api/health` after deployment and inspect logs when troubleshooting
