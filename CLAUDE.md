# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Arboris-Novel is a commercial AI-assisted long-form Chinese fiction writing platform. It combines a FastAPI (Python 3.11) backend, a Vue 3 + TypeScript frontend, and an optional Go gateway for production traffic, WebSocket progress, reverse proxying, and task dispatch. The creative workflow is: concept dialogue (灵感模式) → blueprint generation → chapter outline → context planning and retrieval → AI chapter generation → review/selection → memory and vector persistence for future context. The commercial layer adds membership tiers (`free` / `creator` / `flagship`), multi-channel login, and Alipay/WeChat/Stripe payments — all runtime-configured through the admin panel (SystemConfig table), not env vars.

## Common Commands

### Backend Development
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # then edit .env with real values
uvicorn app.main:app --reload  # starts on http://127.0.0.1:8000
```
`backend/start-dev.sh` / `stop-dev.sh` provide a scripted alternative (tmux uvicorn window + a local redis container). Celery was fully removed (2026-06-10) — async generation goes through the Go gateway.

### Testing
```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt  # pytest/pytest-cov/pytest-asyncio (kept out of the prod image)
pytest                           # run all tests (~80 test files in tests/)
pytest tests/test_prompt_service.py  # run specific test file
pytest -v                        # verbose output
pytest -k "test_name"            # run tests matching pattern
```
No pytest config file — zero-config discovery of `tests/`. Settings load from `backend/.env`; `SECRET_KEY` and `ADMIN_DEFAULT_PASSWORD` must be set there (or exported) or import fails. CI runs with `DB_PROVIDER=sqlite`. `tests/conftest.py` provides an async in-memory-SQLite `db_session` fixture for `@pytest.mark.asyncio` tests (requires `pytest-asyncio`, installed alongside pytest in CI).

### Frontend Development
```bash
cd frontend
npm install
npm run dev          # dev server (0.0.0.0:5000) with HMR
npm run build        # type-check + production build
npm run build-only   # skip type-check, just vite build
npm run type-check   # vue-tsc type checking only
npm run test:unit    # vitest run (config: vitest.config.ts; node env by default, use // @vitest-environment jsdom per-file for DOM)
npm run format       # prettier formatting on src/
```
Vite dev proxies: `/api` → FastAPI :8000; `/tasks` and `/ws` → Go gateway :3000. WebSocket progress and task dispatch in dev require the Go gateway running locally.

### Database Migrations (Alembic)
```bash
cd backend && source .venv/bin/activate
alembic revision --autogenerate -m "describe change"
alembic upgrade head
# existing DBs created by create_all: alembic stamp head
```
Baseline revision: `migrations/versions/3d0894d473c4_baseline_schema.py`. Startup still runs `init_db()` `create_all` + repair helpers; Alembic is the versioned-migration path going forward. (`deploy/scripts/run_migrations.sh` is a separate legacy raw-SQL path using `backend/db/migrations/*.sql` — do not confuse the two.)

### Docker Deployment
```bash
cd deploy && cp .env.example .env  # template lives at deploy/.env.example
docker compose up -d               # app (single container :80) + qdrant
```
`SECRET_KEY` and `MYSQL_PASSWORD` are mandatory `${VAR:?}` interpolations in `deploy/docker-compose.yml` — they must be set in `deploy/.env` even when running `DB_PROVIDER=sqlite`. `docker-compose.prod.yml` is the horizontal-scale stack (nginx + 2×Go gateway + 3×app + mysql + redis + qdrant).

Health check: `GET /api/health`

### CI (`.github/workflows/ci.yml`)
Three jobs: backend = `pytest tests/ -q --cov=app` on Python 3.12 (sqlite); gateway = `go build ./...` + `go vet ./...`; frontend = Node 22 type-check + `test:unit` + build.

### Logs
Application logs are written to `backend/logs/`:
- `app.log` — general application logs (10MB rotation, 5 backups)
- `llm.log` — LLM API calls and responses (20MB rotation, 10 backups); auth headers are masked (`app/utils/llm_tool.py:_mask_headers`), but request bodies (prompts) log a 2000-char plaintext preview
- `trace.log` — lightweight per-stage generation spans as JSON lines (logger `arboris.trace`); grep by `trace_id` to reconstruct one chapter generation's stage timeline (span / duration_ms / seq / status). Emitted via `app/utils/tracing.py` + `GenerationTelemetryService.mark_stage`.

## Architecture

### Backend (`backend/app/`)

Layered architecture: **Routers → Services → Repositories → Models**

- `main.py` — FastAPI entry, lifespan (DB init + prompt preload), middleware stack (HTTPS redirect when not debug, CORS, rate limit, 10MB request-size limit, security headers, request-id), router registration
- `api/routers/` — 22 router modules. Key routers: `writer.py` (advanced generation, SSE, batch generation, finalize/select/evaluate, outline/prediction, summaries, RAG rebuild, archives, diagnostics), `novels.py` (project/concept/reference workflows incl. 灵感模式 endpoints), `auth.py` (password/JWT + WeChat/Google/Linux.do OAuth + phone-code login), `payment.py` (Alipay/WeChat/Stripe orders + webhooks), `plans.py` (plan CRUD + public plans with capabilities), `quota.py`, `api_usage.py` (LLM usage stats), `admin.py` (admin panel: system configs, LLM channel test, user subscriptions), `task_worker.py` (Go dispatcher worker adapter), `writer_progress.py` (backend-local chapter progress WebSocket — separate from the gateway `/ws` hub), `review.py` (six-dimension / consistency / gatekeeper review APIs), `model_catalog.py` (frontend tier-filtered model list + credit balance, admin model-catalog CRUD)
- `services/` — 110+ service modules. Core services used in chapter generation:
  - `pipeline_orchestrator.py` — traditional pipeline orchestrator: config → context/evidence → prompt assembly → generation flow → finalize/archive/telemetry
  - `pipeline_config_service.py` — resolves `fast` / `standard` / `premium` presets, global settings, and request overrides
  - `context_planner_service.py` — builds `ContextPlan` retrieval, prompt, verification, and token-budget tasks
  - `evidence_router_service.py` — routes local plot, global arc, state, and symbolic evidence and enforces evidence budgets
  - `generation_context_resolution_service.py`, `generation_evidence_stage_service.py`, `generation_prompt_context_service.py`, `generation_prompt_stage_service.py` — generation-stage context and prompt assembly helpers
  - `fast_generation_flow_service.py`, `standard_generation_flow_service.py`, `literary_generation_flow_service.py` — execution branches (selected by config booleans, see pipeline section)
  - `single_version_generation_service.py`, `version_generation_service.py`, `standard_post_processing_service.py`, `generation_finalize_service.py`, `generation_background_task_service.py` — generation, post-processing, and follow-up writes
  - `llm_service.py` — unified LLM layer (see "LLM Layer" below)
  - `novel_service.py` — novel CRUD and business logic
  - `chapter_context_service.py` — **active** RAG retrieval entry point (multi-query retrieval + optional reranker)
  - `vector_store_service.py` — Qdrant vector DB operations (chunk/summary storage and retrieval)
  - `writer_shared.py` — shared utilities (mission generation, guardrail rewriting)
  - `chapter_post_processor.py` — post-selection processing (summary + vector storage)
  - `finalize_service.py` — chapter finalization (memory layer, snapshots)
  - `writing_archive_service.py` — 奏折 archive system (generation history)
  - Conditional pipeline services: `humanization_service.py`, `prose_sculptor_service.py`, `consistency_service.py`, `foreshadowing_service.py`, `enrichment_service.py`, `pacing_controller.py`
  - Quality/verification services: `gatekeeper_review_service.py` (quality gate: overall ≥70, each dimension ≥50, ≤2 critical issues), `narrative_claim_service.py` + `narrative_verifier_service.py` (claim-level narrative verification), `scene_generation_service.py`, `novel_bench_service.py` (regression snapshots)
- `agents/` — Agent system (see "Agent System" below)
- `models/` — SQLAlchemy ORM model files covering projects, conversations, blueprints, chapters, versions, reviews, users/quotas, payments/plans, credits (`credit_log`) and model catalog (`model_catalog`), prompts/config, memory layers, chapter blueprints, constitution, factions, power systems, entity registry, foreshadowing, reference novels, archives, templates, writer persona, usage metrics, and update logs
- `skills/` — Writing skill implementations: `platinum_style.py`, `dialogue_polish.py`, `rhythm_control.py`, `foreshadowing.py`, `emotion_boost.py`, `consistency_check.py`
- `schemas/` — Pydantic request/response schemas
- `core/config.py` — `Settings` class (pydantic-settings), loads from `.env`. Key property: `sqlalchemy_database_uri` auto-builds connection string based on `DB_PROVIDER`
- `core/feature_gating.py` — membership capability registry (see "Commercial Layer" below)
- `prompts/` — 39 Markdown prompt templates (concept, outline, chapter plan, writing variants, editor/review/evaluation, foreshadowing, optimization, reference extraction/fusion, mission/persona, outline_revision, screenwriting + screenwriting_outline for the two-stage blueprint, etc.), loaded into DB at startup by `PromptService.preload()`

### LLM Layer (`services/llm_service.py`)

- **Config source**: runtime LLM config reads the `system_configs` DB table first (admin panel → `ApiManagement.vue`), falling back to env vars only when a key is absent (`llm.api_key` → `LLM_API_KEY` style). `OPENAI_*` env vars are only **seed values** written into SystemConfig at startup (`db/system_config_defaults.py`).
- **Channels** (SystemConfig key prefixes, each with `api_key/base_url/model/api_format/reasoning_effort`, unset fields fall back to `llm.*`): `llm.*` default, `llm_optimize.*` polish, `llm_grader.*` evidence grading (silently skipped if unconfigured), `llm_search.*` web-search-capable channel (503 if unconfigured), `embedding.*`/`ollama.*` vectors. Exit methods: `get_llm_response`/`generate`, `get_optimize_llm_response`, `get_grader_llm_response`, `get_search_llm_response`. `llm_fallback.*` is the failover channel: when the default channel fails terminally (any error except the 429 daily-limit) and no streaming delta has been emitted yet, `get_llm_response` retries once on it (`api_type="fallback"` in usage stats); unset with no `llm_fallback.api_key` = disabled.
- **API formats**: `openai` / `anthropic` / `anyrouter` / `gemini` / `openai-responses`; `api_format=auto` infers from model name (claude→anthropic, gemini→gemini, gpt-5→openai-responses). Clients are LRU-cached per format|base_url|key-hash.
- **Reasoning-model compat**: unified think-model detection (`_is_openai_reasoning_model` regex `^o[1-9]`, Claude thinking models); o-series drops `temperature`/`top_p`; retry loop self-heals on `max_completion_tokens` requirement, unsupported `response_format`/`stream_options` (learned per-target in process-level sets), and auto-switches between chat/completions ↔ Responses endpoints. `reasoning_effort` (minimal/low/medium/high) is per-channel configurable and only sent to o-series/gpt-5 on openai formats.
- **Usage metering**: real token usage requested via `stream_options.include_usage` (incl. reasoning tokens), falling back to CJK-aware estimation; aggregated per (date, model, api_type) into `ApiUsageLog` via portable upsert (`services/api_usage_recorder.py`); queried at `/api/api-usage/*`. Default channel enforces per-user daily request limit (429) when configured.
- **Structured output, two-layer strategy**: stable-schema call sites use `generate_structured(prompt, schema)` (json_object + repair + Pydantic validation + error-feedback retry; soft-fail via `default`); everything else uses `json_utils.parse_llm_json(raw, default)` (strip think tags → strip md fences → json_repair → loads). **Never write `content.find('{')..rfind('}')` brace-slicing.**
- **Output sanitization**: `json_utils.is_probable_chapter_plain_text` gates final chapter text (rejects analysis/task-echo output) — see pipeline section.
- **Embeddings**: `get_embedding`/`get_embeddings_batch` return `[]` on any failure (callers must check); misconfiguration guard skips calls when no dedicated embedding key and default base_url isn't a known embedding-capable host.
- **Channel testing**: `POST /api/admin/test-llm-channel` → `LLMService.test_channel` performs a real minimal call per channel, returns `{ok, model, latency_ms, detail}`. Testable channels: `default/fallback/polish/search/grader/embedding/rerank` (`rerank` is not an LLM channel — `test_channel` forwards to `rerank_utils.test_rerank_connection`).

### Commercial / Membership Layer

- **Tiers**: `free` < `creator` < `flagship`. No subscription table — membership state is fully derived from `UserQuota` (`is_premium`, `premium_expires_at`, `plan_tier`); `effective_tier` falls back to `free` on expiry. `QuotaService._derive_tier` maps a paid plan to a tier (explicit `Plan.tier` → plan-name keywords 旗舰/创作者 → default creator).
- **Feature gating (single source of truth)**: capability metadata lives in **code** — `core/feature_gating.py` `CAPABILITIES` registry (currently: `muse_persona`/`muse_search`/`preset_standard` = creator+, `muse_divergence`/`preset_premium` = flagship). Tier mapping lives in **data** — `Plan.tier` + SystemConfig `feature_gating.min_tier_overrides` (JSON) can override minimum tiers. The same registry drives both gate checks (`tier_allows`) and pricing-page capability display (`capabilities_for_tier` → `/api/plans/public`), so marketing copy can never drift from real unlocks. Gate styles differ: concept-converse degrades silently (persona→default, search skipped); `/concept/diverge` and generation presets return 403.
- **Flow-override switch gating (same pattern)**: explicitly enabling pipeline switches via `flow_config` is tier-gated by `FLOW_OVERRIDE_SWITCHES` (defaults: premium-characteristic switches like `enable_optimizer`/`enable_scene_by_scene` = flagship; standard-characteristic like `enable_enrichment` = creator; cost-reducing switches ungated). `enable_polish` is deliberately **not** in this registry — polish is a pure credit-billed add-on (any tier with credits can buy it, see Credits below). Effective tiers are overridable via SystemConfig `feature_gating.flow_override_min_tiers` (JSON). Enforced by `ensure_flow_overrides_allowed` at all four generation entries; only explicit `True` is checked (off/None always pass). Admin panel: 「能力门控」(`FeatureGatingConfig.vue`) edits both override keys; registries exposed at `GET /api/plans/capabilities`.
- **Auth**: besides password (`/api/auth/token`), supports email-code register/reset, Linux.do OAuth, WeChat website QR (`qrconnect`), Google OAuth, and phone-code login-as-register. Each method is toggled by SystemConfig keys (`auth.wechat_enabled` etc.); `GET /api/auth/options` aggregates toggles for the frontend. OAuth/phone first login auto-creates accounts with `external_id` like `wechat:{unionid}` / `google:{sub}`. Codes live in Redis (5min TTL, 60s rate-limit) with in-memory fallback; SMS via `services/sms_service.py` (`sms.provider=aliyun|mock`, mock just logs). Verification-code **email** is dual-channel via `AuthService._send_email` dispatch: SystemConfig `email.provider=smtp|resend` (default `smtp`) selects `_send_via_smtp` (stdlib `smtplib`, `smtp.*` keys) or `_send_via_resend` (raw httpx `POST https://api.resend.com/emails`, `resend.api_key`/`resend.from` keys — `from` domain must be Resend-verified). Both share `_build_verification_email_html`; missing channel config → 500「未配置邮件服务」. `is_active` is checked on every login path.
- **Payments**: `payment.py` + `payment_service.py`, three channels — Alipay (python-alipay-sdk page pay), WeChat Pay (wechatpayv3 NATIVE QR), Stripe (Checkout Session via raw httpx, hand-rolled HMAC-SHA256 webhook verification with 5-min timestamp tolerance, activates only on `payment_status=='paid'`). Channel config in SystemConfig `pay.{alipay|wechat|stripe}.*` (`enabled=='true'`). All callbacks verify signature + amount + idempotency. Activation chain: `_activate_membership` → expiry by `plan.period` (monthly/yearly/forever) → `QuotaService.upgrade_to_premium(user_id, expires_at, plan)`. Admin can grant subscriptions manually (`channel='admin'`, amount 0).
- **Credits (积分制) + Model Catalog**: on top of tiers, generation is metered in **credits**. Balance lives on `UserQuota` (`credit_balance`, `monthly_credit_grant`, `credit_carryover` — default reset-to-zero monthly, `credit_reset_at` rolling-reset anchor); `Plan.monthly_credits` sets the per-plan grant written on activation (0 = tier default via `QuotaService._credit_grant_for_tier`). Every deduction/refund/grant is one `CreditLog` row (`credit_logs`), with a `(reason, ref_key)` unique constraint for **idempotency** and a `balance_after` snapshot. `ModelCatalog` (`model_catalog`) maps a frontend-selectable "模型" (章鱼1.0/2.0/3.0 = octopus_v1/v2/v3 placeholders) to a real LLM channel (5 keys `real_model/base_url/api_key_ref/api_format/reasoning_effort`, blank → fall back to `llm.*`) + `credit_price` + `min_tier`; admin CRUD + frontend tier-filtered display. Polish is a pure opt-in credit-billed add-on (2026-07-26): standard/premium presets no longer force-enable it — the user's checkbox (`flow_config.enable_polish`) both runs it and bills the surcharge (SystemConfig `credits.price.polish`, default 5); it is not tier-gated, the surcharge is charged even without a `model_code`, and a paid polish is never skipped by the generation time budget (paid-must-deliver). **Billing wiring**: `generation_billing_service.py` (`compute_generation_cost`/`charge_generation` 先扣后跑, 402 on insufficient / `refund_generation` by `ref_key=task_id`, idempotent) and `QuotaService.consume_credits`/`refund_credits`/`has_credits`/`check_and_reset_credit`/`list_credit_logs`. Model tier gate: `core/feature_gating.ensure_model_allowed(session, model_code, effective_tier)` (403 if model `min_tier` > user tier or model inactive). `model_code` → real channel via `LLMService._resolve_config_by_model_code` (returns a `config_override` consumed by `single_version_generation_service`/`scene_generation_service`). **Charging happens on the async production task path only** (`task_worker.py`: gate + charge before dispatch, shielded refund on failure/cancel); the sync/SSE writer path passes `flow_config.model_code` through for **channel selection only** and does not charge. **Backward-compatible**: absent/unknown/inactive `model_code` → cost 0 → no charge, no behavior change. Endpoints: `/api/model-catalog/available` (tier-filtered models + credit balance + polish price), `/api/model-catalog/*` (admin CRUD), `/api/quota/me/credit-logs` (ledger). Frontend: `components/writing-desk/WDModelPicker.vue` (model + polish toggle + balance), `components/CreditLedger.vue` (流水明细), `components/admin/ModelCatalogConfig.vue`, `api/credits.ts` + `api/model_catalog.ts`.
- **Admin panel realities**: usage stats are real (every LLM call increments `UsageMetric` + `ApiUsageLog`); LLM channel test makes real calls; system configs CRUD at `/api/admin/system-configs`. Frontend admin components: `LoginAuthConfig` / `PaymentChannels` / `PaymentRecords` / `MembershipPlans` / `ApiManagement` / `ModelCatalogConfig` / `LLMDiagnostics` (「通道诊断」— per-channel LLM health + real-call telemetry) / `FeatureGatingConfig` / `Statistics` under `frontend/src/components/admin/`.

### Inspiration Mode (灵感模式 / Concept Dialogue)

- **Blueprint generation (2026-07-26 rework)**: core lives in `services/blueprint_generation_service.py` (the `novels.py` endpoint is a thin shell). Two-stage LLM: settings stage (world/characters/golden_finger/foreshadowings/**volumes** 分卷规划, 8192 tok) → outline stage (`screenwriting_outline.md`, 12288 tok, fed a compressed settings digest). Chapter-count assertion is **coverage-based over 1..promised** (LLM number-drift can't pass by item count): <80% coverage → one corrective re-ask with missing ranges, still short → 502 with zero DB writes. Production path is async: task type `blueprint:generate` via the Go dispatcher (frontend falls back to the sync endpoint only on submit-400/404/network-error; 429/5xx surface as errors to avoid double-running). Regeneration is refused (409) once the project has any chapter versions/finalized chapters.
- **Converse hardening (2026-07-26)**: history sent to the LLM is slimmed (assistant records → `ai_message` only, bad JSON repaired on read; storage format unchanged), reference material injection is truncated (800/600/800), the response is schema-validated **before** persisting (bad replies never pollute history; the user message alone is kept), and `is_complete` is suppressed until ≥3 user turns.
- Main flow: `POST /{project_id}/concept/converse` (`novels.py`) — single LLM call (temp 0.8), system prompt layered in fixed order: `prompts/concept.md` base (persona 「文思」 + 缪斯心法 divergence principles + rule-0 opening mini-proposals) → reference-novel context/fusion DNA → exclusions → muse persona block (prepended, "SOUL highest priority") → cross-domain material (first turn only) → inspiration spark card (every turn) → JSON output instruction. Returns `{ai_message, ui_control, is_complete}`; `is_complete` sets `ready_for_blueprint=True`.
- Four services: `inspiration_spark.py` (18 Oblique-Strategies-style perturbation cards, one random per turn, `disable_spark` opt-out), `muse_persona.py` (5 persona skins; default = empty injection), `muse_material_service.py` (one-shot web-search via `get_search_llm_response`, returns None on any failure — deliberately no AgenticLoop), `concept_divergence_service.py` (2 LLM calls: high-temp N divergent seeds → low-temp 3-axis scoring novelty/marketability/coherence → top-K).
- Endpoints: `GET /concept/personas` returns `{personas, tier, features, capabilities}` — the frontend's single source for gating UI; `POST /{project_id}/concept/diverge` (flagship-only, 403 otherwise).
- Frontend: `InspirationMode.vue` — 「缪斯设定」 panel (persona dropdown, search/spark toggles, tier badge) + 「✨给我5个狂点子」 divergence button with seed cards that feed back into the conversation.

### Frontend (`frontend/src/`)

Vue 3 + TypeScript + Naive UI + TailwindCSS 4 + Pinia

- `router/index.ts` — auth guards (`requiresAuth`, `requiresAdmin` meta); third rule: admins with `must_change_password` are force-redirected to `/admin?tab=password`; unauthenticated → `/` (landing), non-admin → `/home`
- `views/` — 16 page components. Core: `WorkspaceEntry.vue`, `NovelWorkspace.vue`, `InspirationMode.vue`, `NovelDetail.vue`, `WritingDesk.vue`, `AdminView.vue`, `AdminNovelDetail.vue`, `SettingsView.vue`, auth/legal/pricing pages. `Login.vue` renders password + phone-code + OAuth entries dynamically from `GET /api/auth/options` (via `stores/auth.ts` getters)
- Pricing vs purchase are split: `PricingView.vue` is marketing (capability lists are dynamic from `/api/plans/public`, but its CTA only shows a "coming soon" dialog); the real order UI is `components/SubscriptionPanel.vue` (in `SettingsView`) calling `paymentApi.createOrder`
- `components/` — 70+ Vue components organized by feature (`writing-desk/`, `novel-detail/`, `admin/`, `shared/`, plus top-level project/blueprint/reference/persona components)
- `stores/` — Pinia stores: `auth.ts`, `novel.ts`
- `api/` — 15 client modules; `payment.ts` derives subscription state from `GET /api/quota/me` (no subscription endpoint exists); prefixes are `/api/payment` and `/api/plans`; `credits.ts` + `model_catalog.ts` back the credits/model-catalog UI
- `composables/` — `useAsyncGeneration.ts`, gateway WebSocket progress `useWebSocket.ts`, `useAlert.ts`
- Path alias: `@` → `frontend/src/`

### Database

- **MySQL 8.0+** (default): production-ready, async via `asyncmy`
- **SQLite**: zero config alternative, file at `storage/arboris.db` (set `DB_PROVIDER=sqlite`)
- `DATABASE_URL` (env) overrides `DB_PROVIDER` entirely; postgres URLs are normalized to asyncpg (asyncpg is in requirements), though the `DB_PROVIDER` validator itself only accepts mysql|sqlite
- **Qdrant** (optional): vector DB for RAG, stores `rag_chunks` (text embeddings) and `rag_summaries` (chapter summary embeddings); also used by Mem0 for long-term memory
- All DB access is async (aiosqlite / asyncmy). Session factory: `db/session.py` → `AsyncSessionLocal` (SQLite connections enable `PRAGMA foreign_keys=ON`)
- Tables are bootstrapped via `init_db()` `create_all` plus startup repair helpers (column/index backfill, default prompts). Alembic is configured (`backend/alembic.ini` + `migrations/` with baseline `3d0894d473c4`) as the versioned-migration path — see Common Commands.
- PK type `BIGINT_PK_TYPE` uses `BigInteger().with_variant(Integer, "sqlite")` so autoincrement works on the SQLite dev backend.

### Agent System (Custom Advanced Multi-Agent)

The project supports two execution modes via `HybridExecutor` (`agents/hybrid_executor.py`):

1. **Traditional Pipeline** (`PipelineOrchestrator`) — default service-first generation path, the only real generation engine.
2. **Agent System** (`WritingAgentSystem`) — opt-in sequential wrapper, marked "保留，但不推荐使用" in `writer.py`. `Taizi` parses, optional `Hubu` injects skills, `Zhongshu` plans/contextualizes, `Bingbu` generates through `generation_bridge.py` and `PipelineOrchestrator`, `Menxia` reviews. `PERMISSION_MATRIX` and message-bus routing have been removed; routing is return-value driven. `agentic_loop.py` / `context_manager.py` / `agents/tools/` provide optional tool-use loop support when `use_agentic_loop` is enabled.

```
需求解析 (Taizi) → 技能增强 (Hubu, optional) → 上下文规划 (Zhongshu)
  → 章节生成 (Bingbu → PipelineOrchestrator) → 质量审核 (Menxia)
```

Toggle: `flow_config.use_agent` on `/advanced/generate` requests (`use_agent_system` is the field name only on the Go task path `TaskConfig` / `AsyncGenerateChapterRequest`).

### RAG Pipeline

Active access layer: `ContextAccessService` + `ChapterContextService`. Single-query retrieval uses `retrieve_for_generation()`; evidence/tool paths use `retrieve_multi_query()`. The old `KnowledgeRetrievalService` / `rag_mode=two_stage` implementation is removed. `rag_retrieval_mode` controls vector vs hybrid retrieval, and `EvidenceRouterService` produces evidence packs, budget reports, summaries, and telemetry used by downstream generation stages.

1. Build multiple query strings from outline_title, outline_summary, writing_notes, character names
2. `ChapterContextService` → `VectorStoreService` → vector similarity search: top-K chunks (default 5) + top-K summaries (default 3)
3. Optional **reranker**: hybrid path fetches 2×top_k then reranks via a Jina-compatible API (`utils/rerank_utils.py`). Config is **SystemConfig `rerank.enabled/api_url/api_key/model`** (admin panel 「接口管理 → 重排序模型」, with a real-call 「测试连接」 button); `RAG_RERANKER_*` env vars are seeds only. Base URLs get `/rerank` appended automatically; url/key fall back to `embedding.base_url`/`embedding.api_key` when unset. A per-URL failure latch (3 consecutive failures) extinguishes rerank **per process** so a dead endpoint can't burn a round-trip on every retrieval — a successful call or a successful admin test clears it (only in that process).
4. Retrieved content injected into LLM prompt alongside blueprint + previous chapter summaries
5. After chapter finalization: text split (LangChain `RecursiveCharacterTextSplitter`, 480 chars/120 overlap) → embed → store in Qdrant
6. Optional hybrid mode: `HybridRetrievalService` (Vector + BM25 + RRF fusion), activated only when `rag_retrieval_mode="hybrid"`

### Chapter Generation Pipeline (Traditional)

```
Request → TierGate(preset vs effective_tier) → ConfigResolve → ContextAssembly(parallel prefetch)
  → MissionGeneration → StrategyResolve(evidence stage)
  → flow branch:
      fast:     single version + rule-based humanization + optional polish + length compression + entity-alias replacement
      standard: GenerateVersions(×N parallel) → AI review picks best (only if N>1)
                → post-processing chain on best: combined_revision(review flaws + self-critique)
                  → consistency + humanization → optimizer/polish(opt-in, credit-billed)/enrichment/density
                  → sync six-dimension review (auto-refine below threshold) → guardrail re-check
      literary: scene-by-scene + ProseSculpt (only reachable via explicit enable_scene_by_scene override — no preset enables it)
  → Archive(奏折 complete) → AsyncFollowups(foreshadowing extraction[all] + stage-B analysis
      + state tracking(CharacterState/Timeline, no mem0)[standard+] + full memory update incl. mem0[premium]
      + ChapterPostProcessor summary/vectors[standard only])
```

- **Branch dispatch is by config booleans, not preset strings**: `enable_scene_by_scene` → literary, `enable_fast_path` → fast, else standard. Preset mapping: `fast`→fast branch; `standard`/`premium`→standard branch (premium enables more switches but forces `version_count=1`, so multi-version + AI selection only actually happens on `standard`).
- **Long-range memory injection (2026-07-26)**: non-fast paths inject `[卷级前情]` (current + prev 2 volume summaries) and `[全书脉络]` (book summary) as dedicated prompt sections via DB-direct prefetch (5s degrade) — no longer telemetry-only; `[项目长期记忆]` is unlocked for standard; `[角色当前状态]` is real on standard+ via `enable_state_tracking` (lightweight CharacterState/Timeline writes without mem0; full memory incl. mem0 stays premium). `enable_temporal_state` is wired (snapshot supplements, never replaces, the structured state outputs). Story skeleton far-chapter sampling prioritizes chapters with unresolved foreshadowing (2 slots reserved for first/last anchors); summary backfill is capped (recent 30, concurrency 5, 180s total wall-clock) with outline-fallback for skipped chapters.
- **Tier gate, not quota**: `/advanced/generate`, `/stream`, `/advanced/batch-generate`, and the Go task path all call `core/feature_gating.ensure_generation_preset_allowed` (fast=free, standard=creator+, premium=flagship+, 403 on violation; legacy alias names are normalized first via `normalize_preset` so they cannot bypass the gate). There is **no** daily-quota check/consume on the generation path (`check_chapter_quota`/`consume_chapter_quota` have zero callers). The same entries also run `ensure_flow_overrides_allowed` so `flow_config` switches can't grant higher-tier pipeline features (see Commercial Layer).
- **Config resolution order** (`PipelineConfigService.resolve_config`): preset block → global settings overrides (`writer_fast_mode` forces fast; `writer_ultra_fast_mode` trims post-processing) → request `flow_config` allowlisted overrides.
- **Output sanitization gate**: final text is validated by `is_probable_chapter_plain_text`; invalid direct generation triggers one lower-temp hard-constraint retry, then HTTP 502. Optimizer/polish results are validated the same way and fall back to the pre-step text.
- **SSE**: `/advanced/generate/stream` wraps the same executor in a producer task + queue (own DB session); emits telemetry events + per-token text deltas (fast branch), `: ping` keepalive every 15s, terminal `completed` event carries the full response.
- **Async path (production)**: Go Dispatcher → `POST /api/internal/tasks/execute` (`task_worker.py`, `X-Internal-Secret` callbacks) → same `HybridExecutor`. The same tier gate runs here before dispatch; a too-high preset fails the task with the 403 detail and `permanent: true`, which the Go dispatcher honors by skipping retries. This is also **the only path that meters credits**: `ensure_model_allowed` + `charge_generation` (先扣后跑) before execution, shielded `refund_generation(ref_key=task_id)` on failure/cancel (see Credits + Model Catalog above). The sync/SSE path selects the model channel from `flow_config.model_code` but does not charge.
- **Vector timing**: standard branch vectorizes immediately via async ChapterPostProcessor; fast/literary defer to `/chapters/select` or finalize. `FinalizeService` always skips vector updates (vectors are ChapterPostProcessor's job).
- `GatekeeperReviewService` is **not** in the generation pipeline — it backs the standalone `/api/review/gatekeeper` endpoint and `MenxiaAgent`.

### Go Gateway (Phase 2)

Production architecture: Nginx → Go Gateway → Python FastAPI Workers
- `gateway/cmd/gateway/main.go` — **the single production entry** (JWT, rate limit, WebSocket Hub, reverse proxy, Prometheus metrics). Forwards gateway-verified identity to FastAPI via `X-Gateway-*` headers (client-supplied copies are stripped).
- Go Task Dispatcher: `/tasks/submit`, `/tasks/:id/status`, `/tasks/:id/cancel`, `/tasks/user/:user_id`, `/tasks/stats`, concurrency control, worker pool, progress push via Redis Pub/Sub. Task types are an **enum in Go** (`chapter:generate` / `chapter:batch_generate` / `blueprint:generate`(15m timeout, no credit billing)) — new types must be registered in `taskdispatcher` or submit returns 400 (the frontend treats submit-400 as "old gateway" and falls back to the sync endpoint)
- Python worker adapter: `backend/app/api/routers/task_worker.py`; gateway worker progress callback: `/internal/tasks/:id/progress`, shared secret `TASK_DISPATCHER_INTERNAL_CALLBACK_SECRET` ↔ gateway `task_dispatcher.internal_callback_secret`
- **Removed (2026-06-01)**: `internal/llmgateway` (an untracked residue dir may linger on disk) and the entire `cmd/api` dual-binary subgraph — it duplicated FastAPI domain logic in Go. FastAPI is the canonical domain layer.

### Key Env Variables

Hard-required at startup: `SECRET_KEY`, `ADMIN_DEFAULT_PASSWORD`. (`OPENAI_API_KEY` is optional — LLM runtime config lives in the SystemConfig DB table; env values only seed it at first startup.)

LLM seeds: `OPENAI_API_BASE_URL`, `OPENAI_MODEL_NAME`, `WRITER_CHAPTER_VERSION_COUNT`

Embedding: `EMBEDDING_PROVIDER` (openai|ollama), `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`

Vector DB / RAG: `QDRANT_HOST`, `QDRANT_PORT`, `VECTOR_TOP_K_CHUNKS`, `VECTOR_TOP_K_SUMMARIES`, `VECTOR_CHUNK_SIZE`, `RAG_RERANKER_ENABLED/_API_URL/_API_KEY/_MODEL` (**seeds only** — runtime value lives in SystemConfig `rerank.*`), `RAG_BM25_WEIGHT`, `RAG_MIN_SCORE`, `RAG_DEFAULT_MODE`

DB: `DB_PROVIDER` (sqlite|mysql), `SQLITE_PATH` (not SQLITE_DB_PATH), `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`, `DATABASE_URL` (overrides everything)

Gateway: `TASK_DISPATCHER_INTERNAL_CALLBACK_SECRET` (accepts `GATEWAY_` prefix alias)

## Code Conventions

- Backend uses `# AIMETA` comment headers on key files for AI navigation metadata (format: `P=purpose|R=responsibility|E=entry_point|...`)
- All backend services are async; use `async/await` throughout
- LLM interactions go through `llm_service.py` — never call OpenAI/Ollama directly from routers
- LLM JSON parsing: `generate_structured` for stable schemas, `parse_llm_json` otherwise; never brace-slice raw content
- Prompt templates live in `backend/prompts/*.md` and are synced to DB on startup; edit the `.md` files, not DB records directly
- Membership-gated features: register the capability in `core/feature_gating.py` `CAPABILITIES` and gate via `tier_allows` — never hardcode tier checks
- Runtime/business config belongs in SystemConfig (admin-editable), not env vars; env is for deployment-level settings and seeds
- Frontend uses Naive UI component library — prefer its components over custom implementations
- Frontend styling: TailwindCSS 4 utility classes (PostCSS integration, not `@tailwind` directives)
- Node engine requirement: `^20.19.0 || >=22.12.0`
- Logging: use `logging.getLogger(__name__)` in backend modules; logs route to `backend/logs/app.log`, `llm.log`, or `trace.log` depending on logger configuration
- When adding new agents: register in `WritingAgentSystem._register_agents()` (flow is sequential and return-value driven)

## Known Pitfalls (verified 2026-06-10; 2026-07-26 大规模整改后部分描述已随之更新)

- **2026-07-26 深度审计与五阶段整改**：`docs/generation-quality-audit-2026-07.md` 是当日 ~60 项问题的完整清单与修复状态（阶段 0-4 全部交付）。阅读旧报告/记忆时注意：六维评审、卷/书摘要注入、CharacterState(standard)、temporal_state、polish 计费、蓝图两段+异步等的"修复前"描述均已过时。

- **Preset names**: only `fast`/`standard`/`premium` are real; legacy names (`basic`/`enhanced`→standard, `ultimate`/`platinum`/`literary`→premium) and unknown names (→fast) are normalized at entry by `core/feature_gating.normalize_preset` — the single alias table shared by config resolution and the tier gate. Don't reintroduce a separate mapping; the Go gateway's submit default is also `fast` (`taskdispatcher/handler.go`). (A 2026-06-07 regression made the alias branch recurse infinitely and let aliases/unknown names bypass the tier gate; fixed 2026-06-10, locked by `tests/test_preset_gating.py` + `tests/test_pipeline_config_resolution.py`.) Request-side `versions` is capped at 5 in `writer_shared.resolve_version_count`.
- **`deploy/scripts/`** are environment-specific (hardcoded server IP / repo URL), not a generic deploy flow; `run_migrations.sh` uses the legacy raw-SQL migration dir, not Alembic.
- Multiple agent docs coexist (`AGENTS.md`, `GEMINI.md`, `replit.md`); `AGENTS.md` overlaps this file heavily — when updating architecture facts here, check whether `AGENTS.md` repeats the stale claim.
- Celery was fully removed 2026-06-10 (router `tasks.py`, `app/tasks/`, `app/config/`, requirements, prod-compose worker blocks); if you see Celery references in older docs/reports they are historical.

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
- Frontend viewers `MiddleProductViewer`, `DiagnosticPanel`, `AgentFlowVisualizer` are wired to real data (no longer shells).
