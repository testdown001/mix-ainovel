# AGENTS.md

Guidance for coding agents working in Arboris-Novel.

Last code audit: 2026-10-17. This is a navigation and maintenance guide, not a replacement for reading the affected runtime code.

## Code Discovery Workflow

- Use the installed default `code-index-mcp` server for code indexing, file discovery, search, and structural analysis.
- On entering the repository, or when the index is absent/stale, call `set_project_path` with the current repository root. Do not assume another agent's MCP session shares the selected project.
- Narrow the scope with `find_files`, then use `search_code_advanced` with file-pattern constraints. Prioritize Python for backend behavior and Go for gateway behavior; include TypeScript/Vue when tracing frontend contracts.
- Before understanding a specific file, call `get_file_summary`. If it reports `needs_deep_index`, run `build_deep_index`. Read only the relevant located code rather than scanning directories page by page.
- Some configuration/hidden files are absent from glob discovery but searchable by explicit file pattern. An empty index result alone does not prove that a file or feature is absent.
- Run `refresh_index` after edits, refactors, dependency changes, or renames. If file watching is unavailable, explicitly arrange a manual refresh.
- Keep actual `.env` files, credentials, local databases, generated logs, `node_modules`, and build output out of documentation and commits.

## Project Overview And Source Of Truth

Arboris-Novel is a long-form AI fiction platform:

- **Python FastAPI** owns business APIs, authoring state, LLM orchestration, retrieval, review, billing, and persistence.
- **Vue 3 + TypeScript** provides inspiration, project planning, the writing desk, public reading, subscription/credits, and administration.
- **Optional Go gateway** provides reverse proxying, JWT handling, rate limiting, Redis-backed task dispatch, and WebSocket fanout. It is not a second business backend or an LLM service.

The authoring loop is:

concept dialogue -> blueprint/character/world planning -> volume and chapter planning -> context/evidence collection -> chapter candidates -> quality checks -> explicit author selection/editing -> durable revisions -> memory/state updates -> future retrieval and replanning.

Trust runtime code under `backend/app/`, `frontend/src/`, and `gateway/` over older README/design reports. In particular:

- Generation is service-first, not a single monolithic orchestrator.
- Public presets are `fast / standard / premium`; subscription tiers are `free / creator / flagship`. They are different concepts.
- The vector store is Qdrant, with optional BM25/hybrid retrieval and Mem0 integration; old libsql settings are not current retrieval configuration.
- The Go runtime has one entry point, `gateway/cmd/gateway/main.go`. Do not restore removed `cmd/api`, `internal/llmgateway`, Agent message-bus routing, or stale retrieval stages from historical docs.

### Repository Map

| Area | Responsibility |
| --- | --- |
| `backend/app/api/routers/` | HTTP/WebSocket adapters and dependency/ownership checks |
| `backend/app/services/` | Authoring, generation, review, memory, payment, and admin business logic |
| `backend/app/agents/` | Hybrid executor and ordered writing Agent workflow |
| `backend/app/models/`, `schemas/`, `repositories/` | ORM state, API/internal contracts, and data access |
| `backend/app/core/`, `db/`, `utils/` | Settings, capability gates, bootstrap/defaults, provider helpers, tracing |
| `backend/prompts/` | Source-controlled prompt templates |
| `backend/migrations/` | Alembic schema history |
| `backend/tests/` | Focused Python regression suite |
| `backend/app/services/bench/`, `backend/run_bench.py` | Generation benchmark fixtures, execution, judging, and reports |
| `frontend/src/` | Vue views/components, API adapters, stores, composables, utilities |
| `gateway/internal/` | Gateway auth, proxy, limiter, task dispatcher, WebSocket hub |
| `deploy/` | Container build, standalone/production routing, migration/deployment scripts |
| `docs/` | Design and operational context; verify claims against runtime code |

Avoid fixed file counts in architectural decisions; use indexed discovery when the actual scope matters.

## Development And Validation Commands

### Backend

Run from `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp env.example .env
uvicorn app.main:app --reload
```

Use Python 3.12 to match the app container. Configure a local database and required settings before starting. Tests have shared fixtures in `backend/tests/conftest.py`; test dependencies, including `pytest-asyncio`, are in `requirements-dev.txt`, not the production requirements.

```bash
pytest
pytest tests/test_service_first_regression_matrix.py
pytest tests/test_generation_contract.py tests/test_hybrid_executor_contract.py
pytest tests/test_m2_chapter_reliable_save.py tests/test_regenerate_preserves_chapter.py
pytest -k "test_name"
alembic current
alembic upgrade head
```

Benchmark commands, also from `backend/`:

```bash
python run_bench.py list
python run_bench.py run --scenarios demo_xuanhuan --configs standard --dry-run
python run_serial_bench.py --help
```

A dry run substitutes external model calls; it still needs application settings/database setup. Real benchmark runs generate data and incur model calls. Read CLI options and `docs/bench-guide.md` before running comparisons. Benchmark time budgets differ from production by default; `--respect-time-budget` preserves the production budget behavior.

### Frontend

Run from `frontend/`; Node requirement: `^20.19.0 || >=22.12.0`.

```bash
npm ci
npm run dev
npm run type-check
npm run test:unit
npm run build
npm run check:css
npm run test:e2e
npm run format
```

- `build` runs type checking and `build-only`; `check:css` requires built `dist/`.
- Vite development server defaults to port 5000: `/api` proxies to Python :8000, while `/tasks` and `/ws` proxy to Go :3000.
- Playwright configuration is `frontend/playwright.config.ts`. Build `dist/` first with `npm run build-only` or `npm run build`; the smoke runner does not build it. It starts a same-origin Python app through `frontend/e2e/start-backend.sh`, with a temporary SQLite database and seeded user. Default port is 8130 (`E2E_PORT` overrides it). Smoke tests do not require real LLM calls.

### Gateway

Run from `gateway/`; `go.mod` and the Docker builder target Go 1.25.

```bash
go mod download
go test ./...
go build ./cmd/gateway
go run ./cmd/gateway
```

The gateway requires Redis. Configuration comes from `config.yaml` (or `CONFIG_PATH`) plus bound `GATEWAY_*` environment overrides in `internal/config/config.go`.

### Deployment

Use `deploy/.env.example` as the Compose configuration template.

```bash
cd deploy
cp .env.example .env
docker compose up -d --build
# Production topology:
docker compose -f docker-compose.prod.yml up -d --build
```

These are separate topologies; inspect their required variables before switching. The standalone stack defaults to an external MySQL host; selecting SQLite does not remove all Compose-required variable interpolation.

For recorded release identity, use the deployment scripts or the `build` -> Compose build -> `deploy` -> Compose `up --no-build` sequence in `docs/admin-release-info.md`. Source `deploy/scripts/prepare_release_metadata.sh` in the same shell. Direct builds without metadata remain supported and report unknown values. Image `/app/release-info.json` is immutable build identity; only an explicit deployment records the shared event. Restart/recreate and database restore must not refresh it. `deploy/.release.env` is ignored non-secret metadata, never shell-source it; only three deployment keys are updated in the existing configuration `.env`.

For container migrations, prefer `bash deploy/scripts/run_migrations.sh` from the repository root. It uses the app's configured database, backs up MySQL, and validates legacy schema shape before allowing a stamp. Never blindly `alembic stamp head` to silence missing-column errors.

Health endpoints: Python `GET /api/health`; Go `GET /health`.

## Backend Entry Points And Boundaries

### Boot And API Registration

- `backend/app/main.py`: app/lifespan assembly, database initialization, prompt preload, startup diagnostics, subscription reminders, and LLM-call-log cleanup.
- Middleware includes request ID, rate limiting, a 10 MB request-size cap, security headers, and CORS. HTTPS redirect is enabled in non-debug mode unless `FORCE_HTTPS_REDIRECT=false`; Compose disables it by default for upstream TLS termination.
- When frontend build assets exist, Python can serve the SPA. Entry HTML is not aggressively cached; this works with frontend stale-chunk recovery.
- `backend/app/api/routers/__init__.py` is the active router registry. Discover registrations there rather than relying on the list in older reports.

Important router responsibilities:

| Router file | Main responsibilities |
| --- | --- |
| `novels.py` | Projects, concept dialogue/blueprints, characters/world/volumes, chapter authoring/history/export, cover and reference integration |
| `writer.py` | Generation, SSE, batch work, outline tasks, selection/finalization, diagnostics, archives and rebuilds |
| `task_worker.py` | Authenticated internal worker adapter used by the Go dispatcher |
| `writer_progress.py` | Backend-local chapter progress WebSocket and pause/resume/status |
| `auth.py` | Password/JWT, auth options, OAuth and phone-code login |
| `quota.py`, `plans.py`, `payment.py` | Quotas/credits, membership/capabilities, payment orders/callbacks |
| `model_catalog.py`, `api_usage.py` | User model choices/pricing and LLM usage reporting |
| `admin.py` | User/project operations, runtime config, provider diagnostics and administration |
| `public_share.py` | Token-based public reading, separate from authenticated authoring |
| `creative_memory.py`, `skill.py` | Creative-memory and writing-skill operations |
| `reference_novels.py`, `review.py`, `optimizer.py` | Reference library, review, and text optimization |

Keep router changes thin; follow ownership checks through the service/repository layer. Public share access must not expose private authoring/history/admin endpoints.

### Generation Stack

User-facing generation enters through `writer.py` or `task_worker.py`, then `agents/hybrid_executor.py`. The traditional branch delegates to `services/pipeline_orchestrator.py`; the Agent branch uses `agents/system.py`. Both must preserve the unified response in `schemas/generation_contract.py` (`normalize_generation_result`).

Key service groups, all under `backend/app/services/`:

| Stage | Primary files |
| --- | --- |
| Config/policy/billing | `pipeline_config_service.py`, `generation_policy_service.py`, `generation_billing_service.py` |
| Typed context/planning | `generation_state.py`, `context_planner_service.py`, `mission_builder_service.py`, `generation_support_service.py` |
| Context access/history | `context_access_service.py`, `chapter_context_service.py`, `generation_context_resolution_service.py`, `enhanced_context_service.py`, `history_context_service.py` |
| Evidence | `generation_evidence_stage_service.py`, `evidence_router_service.py`, `evidence_grader_service.py` |
| Prompt assembly | `generation_prompt_context_service.py`, `generation_prompt_stage_service.py`, `prompt_assembly_service.py`, `prompt_compiler_service.py`, `writer_prompt_service.py` |
| Candidate execution | `single_version_generation_service.py`, `version_generation_service.py`, `scene_generation_service.py` |
| Execution branches | `fast_generation_flow_service.py`, `standard_generation_flow_service.py`, `literary_generation_flow_service.py`, `standard_post_processing_service.py` |
| Result/quality/finalization | `generation_result_service.py`, `generation_quality_gate.py`, `generation_finalize_service.py`, `finalize_service.py` |
| Follow-up work | `generation_background_task_service.py`, `generation_analysis_task_service.py`, `generation_write_task_service.py`, `chapter_post_processor.py` |
| Telemetry/progress | `generation_telemetry_service.py`, `writer_progress_service.py`, `backend/app/utils/tracing.py` |

Contracts to preserve:

- `generation_state.py` currently defines `PreCollectedContext`, not a `GenerationState` class. Reuse typed collected context instead of repeating retrieval in every stage.
- Normalize historical preset aliases through `core/feature_gating.py`; do not create parallel compatibility mappings.
- `premium` normally selects scene-by-scene execution, implemented by the literary flow service. The filename `literary` is not an additional public preset.
- Explicit polish is a separately priced option, not automatically enabled by a preset. Enabling it can resolve to the standard post-processing branch unless scene flow is explicitly overridden. Use the resolver, not frontend assumptions.
- Non-fast results pass the shared quality gate before candidate persistence. Preserve chapter guardrails, truncation/empty-output checks, failure metadata, and refund behavior.
- The existing non-fast check also requests an optional narrative delta. Missing/invalid extraction is separate from prose verification and must not trigger extra model calls; fast/manual/history coverage may be incomplete.
- Time-budget skips are intentional degradations with diagnostic/progress metadata, not silent success of work that never ran.
- Progress completion, stream final payloads, archive writes, and follow-up work must retain their ordering and response contracts.

### Agent Workflow

- `agents/hybrid_executor.py`: execution-mode selection and shared caller contract.
- `agents/system.py`: registry and ordered workflow.
- `agents/base.py`, `agents/message.py`: Agent lifecycle, context/result/capability contracts.
- `agents/generation_bridge.py`: reuse of pipeline generation/review capabilities.
- `agents/agentic_loop.py`, `agents/tools/`: optional tool-use support.

Current writing roles: `TaiziAgent` triages goals; `HubuAgent` applies skills; `ZhongshuAgent` plans and collects context/evidence; `BingbuAgent` generates; `MenxiaAgent` reviews. Keep the registry, registration, execution order, pre-collected context, and result normalization consistent. This is not an autonomous message-bus architecture.

Agent initialization failure can fall back to the pipeline; failure after Agent execution starts does not automatically rerun the request through the pipeline. Preserve this boundary to avoid duplicate work and billing.

### Author-Owned Manuscript And Revision Safety

These rules apply across generation, manual editing, task retries, and frontend recovery:

- `NovelService.replace_chapter_versions()` appends a new AI candidate batch despite its legacy name. It must not delete historical versions or silently replace the author's selected text.
- New candidates carry generation-batch metadata; index-based selection addresses the latest batch. Explicit selection is what promotes a candidate to the author's manuscript.
- Regeneration must preserve `selected_version_id`, `revision_id`, `content_hash`, and the confirmed summary until an explicit author action.
- `chapter_revision_service.py` implements revision/hash compare-and-swap saves. Send both `expected_revision_id` and `expected_content_hash`; preserve idempotent same-content retries.
- Conflicts require an explicit resolution or a saved branch, never unconditional last-write-wins.
- Selection uses stable version IDs plus revision/hash CAS, not a refreshed baseline after generation. Legacy index selection cannot overwrite existing prose without a baseline (428); concurrent changes return 409. Re-adopting the same version is idempotent.
- History listings are paginated metadata; load version content/diff on demand. Restores also validate the baseline.
- Export and public reading must use the intended author-confirmed manuscript, not an arbitrary newest AI candidate.
- Chapter/volume/world-state planning, selected text, review snapshots, and memory are related but distinct state. Do not infer confirmation solely from the presence of generated content.

### Async Work, Streaming, And Recovery

Do not merge these different delivery mechanisms:

1. **Direct SSE generation**: `writer.py` -> `frontend/src/api/novel.ts`, endpoint `/api/writer/advanced/generate/stream`.
2. **Backend-local chapter progress**: `writer_progress.py` + `writer_progress_service.py`; progress/control channel, not the Go task queue.
3. **Go durable tasks**: frontend `api/task.ts` -> gateway `/tasks`; Redis-backed dispatch calls Python `/api/internal/tasks/execute` and publishes events to gateway `/ws`.
4. **Persisted outline work**: `outline_generation_task_service.py` and its model/API track outline planning/generation, cancellation, retry, and checkpoints. These are not interchangeable with Go task IDs or SSE connections. Database checkpoints do not guarantee automatic continuation after process restart. Cancellation waits for the current step; body-generation retries reuse successful outlines.
5. **Canonical derivations and platform repair**: `chapter_derivation_service.py` persists adopted-text jobs transactionally and dispatches them with database leases; `derived_state_repair_service.py` separately executes explicitly budgeted administrator repair batches. Both Python workers start in the app lifespan and work without the optional Go gateway.

Gateway task types include `chapter:generate`, `chapter:batch_generate`, and `blueprint:generate`. Retry creates lineage; batch retry reuses completed checkpoints and retries failed work.

- Worker requests and progress callbacks use the shared `X-Internal-Secret` configuration. Python refuses internal execution when the secret is not configured.
- Validate ownership for task/status/progress access and preserve cancellation/terminal states.
- A disconnected stream or WebSocket is not proof that server generation failed. Reconcile stored chapter/task state before retrying; otherwise duplicate generation or billing can result.
- An application-level permanent error must not be treated as a transient transport failure and blindly retried.

## Planning, Memory, Quality, And Inspiration

### Long-Form Continuity

- `narrative_state_service.py` replays narrative deltas from preceding selected versions, not an independent canonical state table. Only verified, content-hash-matching, narrative-lineage-valid deltas enter canon; drafts/recommendations do not. Earlier chapter edits invalidate downstream derived deltas, and conflicting facts are quarantined.
- `reader_action_service.py` defaults to the premium scene branch: propose a small set of beats, score independently, and write only the winner. Failure falls back to the scene contract, not an unverified reference-derived action.
- Character motives, relationships, attachment, significance, and unresolved obligations must survive blueprint -> volume/outline -> mission/prompt transitions. Preserve structured planning fields rather than reducing them to an unrelated prose summary.
- State tracking also spans temporal/entity/character state, foreshadowing, volume/world state, and narrative summaries. Trace consumers before adding duplicate extractors.
- Quality-loop features include rolling outline revision, volume retrospective/replanning, character significance, and two-pass drafting. SystemConfig `quality_loop.*` values take precedence over environment defaults (all four default off). Premium reads these settings; explicit flow overrides still require gating. Two-pass is on the generation path, while the other loops can run asynchronously.
- Canonical memory/state/foreshadowing and future-plan suggestions now follow adopted text through the outbox, not recommended candidates. Candidate review remains draft analysis. Every derived read/write validates source version, content hash, adoption revision and preceding lineage; late results cannot publish.
- Author-requested volume divergence and automatic retrospective replanning share related storage but differ in source and application semantics. Do not apply a suggestion as if the author had accepted it.

### Retrieval And Memory

Start with `vector_store_service.py`, `memory_layer_service.py`, `memory_distillation_service.py`, `chapter_ingest_service.py`, `volume_summary_service.py`, `book_summary_service.py`, and `narrative_summary_service.py`.

- Keep project/user scope, evidence provenance, context budgets, embedding dimensions, and cache invalidation intact.
- `retrieval_scope.py` supplies a server-owned exclusive chapter bound and SQL canon manifest. Scope must reach vector/BM25/by-ID/summary/state/Agent readers; future plans are separate from historical facts. Unknown legacy provenance is not proof of canon.
- Keep cosine, RRF and rerank score domains separate. Only cosine uses `rag_min_score`; hybrid fallbacks must not mix raw cosine with RRF rankings.
- Indexing prepares embeddings, stages an immutable revision, obtains write receipts, then CAS-publishes `Chapter.active_index_revision_id`. Failed/partial writes must not advance `rag_ingest_hash` or delete the last valid index. `embedding_index_config.py` isolates collections by non-secret runtime model/provider/base URL/dimension fingerprint.
- Qdrant retrieval, optional BM25/hybrid/reranking, structured narrative state, and Mem0 are complementary; they are not one universal store.
- Mem0 is pinned to `mem0ai==1.0.4`. A 2.x upgrade requires adapting the memory service `search/get_all` argument contracts.
- Versioned Mem0 writes use `infer=False` through `mem0_compat.py`, carry source metadata, and require a completed SQL receipt; read results are post-validated against current canon. Keep one project-level search, no automatic re-query on filtering, and no legacy semantic distillation of v2 memories. Mem0 is a cache, not the authority.
- Embedding, rerank, and memory configuration may come from runtime config, not only environment variables. Check actual consumers and failure-latch/fallback behavior.
- Reference workflows now involve `reference_project_service.py`, `reference_reading_contract.py`, `reference_runtime_service.py`, `reference_beat_service.py`, `reference_prose_service.py`, and `reference_novel_library_service.py`. Preserve project binding and reading/fusion contracts, not just style snippets.
- FusionDNA v2 validates ordered source IDs and content signatures. Rebinding/reanalysis invalidates stale fusion; incomplete material requires an explicitly provisional fallback. Analysis cards and AI imitation are not evidence from the original full text.

### Review And Benchmarks

Important review modules: `gatekeeper_review_service.py`, `six_dimension_review_service.py`, `narrative_verifier_service.py`, `narrative_claim_service.py`, `consistency_service.py`, and `chapter_guardrails.py`.

Use scene plans, compiled prompts, retrieved evidence, claim verification, and review snapshots when diagnosing continuity. Do not “fix” an upstream evidence omission only by weakening a review prompt.

The benchmark implementation under `services/bench/` supports fixtures, configuration/ablation comparisons, model judging, and serial-reading evaluation. Distinguish these from lightweight `novel_bench_service.py` snapshots. Protect user projects when creating or cleaning benchmark fixtures.

### Inspiration, Skills, And Prompts

- `InspirationMode.vue` integrates muse personas, material discovery, spark injection, and tier-gated concept divergence. Backend support includes `muse_persona.py`, `muse_material_service.py`, `inspiration_spark.py`, and `concept_divergence_service.py`.
- Concept dialogue has a ten-key-round limit. Preserve an existing project when communication fails rather than creating a replacement project or losing the conversation.
- Concept confirmation uses `BlueprintConfirmation.vue` for the editable dossier, stress reports, and suggested fixes; its `StoryVoiceTrial.vue` child loads/generates/selects voice trials. Trace child components before declaring an API-only feature or changing availability/pricing controls.
- `writing_skill_registry_service.py`, `skill_service.py`, the skill router, and `SkillManagement.vue` govern versioned writing skills and project-scoped skill copies, not whole-novel cloning. Generation resolves published server-side snapshots with ownership checks; drafts remain invisible. Rollback creates a new version, and usage receipts retain the exact version. Do not silently mutate a project's copied skill when editing a global template.
- Prompt Markdown under `backend/prompts/` is checksum-synchronized by database bootstrap, then `PromptService.preload()` warms database templates. Source-controlled defaults belong in Markdown; admin customizations are preserved unless explicitly reset. Do not assume a file edit overwrites every existing DB value.
- New schema-shaped LLM outputs should use `LLMService.generate_structured()` and Pydantic validation/retry. For other model JSON, reuse `utils/json_utils.py`, not brace slicing.

## LLM Operations, Billing, Auth, And Administration

### LLM Boundary And Diagnostics

- Route new runtime model interactions through `services/llm_service.py`; provider helpers live under `utils/llm_tool.py`.
- Inspect model catalog selection, runtime channel configuration, and provider dispatch together. User `model_code` and the underlying provider model/channel are not interchangeable.
- Catalog `api_key_ref` names a SystemConfig key, not a plaintext credential. Optional optimize/search/grader channels are enabled by any explicit API key/base URL/model/API format, not reasoning settings alone. When unconfigured, optimize falls back to default, search returns 503, and grader skips scoring.
- Preserve fallback channels, Responses/chat compatibility, reasoning/thinking parameters, streaming delta handling, real usage tokens, truncation detection, and `max_completion_tokens` compatibility.
- Fallback requires its own API key and applies only before any stream delta; 429 and truncated-response errors must not trigger a second streamed generation. Use `utils/llm_capabilities.py` for provider capability decisions rather than historical model-name assumptions.
- `generate_structured()` adds schema validation and validation-error retries; avoid replacing it with unchecked hand-parsed JSON.
- `api_usage_recorder.py` records usage; `LLMCallLog` diagnostics capture call failures/blank replies separately. The startup cleanup retains diagnostic calls for 72 hours; these are not a permanent audit ledger.
- `llm_channel_audit.py` and admin diagnostics distinguish default/fallback/polish/search/grader/embedding/rerank configuration. Inspiration does not imply a separately configured runtime channel. A configured key is not proof that the channel works.
- Keep secrets and raw credentials out of logs, client responses, and documentation.

### Membership, Credits, And Payment

- `Plan.tier` plus `core/feature_gating.py` is the capability source of truth. Runtime minimum-tier and flow overrides exist; never duplicate authorization solely in the UI.
- Subscription status is derived from quota state, not a separate assumed subscription table.
- Model catalog options include tier access and credit prices. Generation, polish, local text transformations, and covers must use backend pricing/options rather than frontend constants.
- `quota_service.py`, `generation_billing_service.py`, payment services, and credit logs must agree on prechecks, deductions, failure refunds, and idempotency.
- Membership credits and permanently purchased credits have separate lifecycles. Subscription changes/expiry must not erase purchased credits.
- Deductions use the monthly pool before purchased credits; monthly periods roll over 30 days, not calendar months. Current failure refunds return to the monthly pool. Preserve `(reason, ref_key)` idempotency and the existing refund contract when changing wallet behavior.
- Missing/inactive `model_code` can make the model component free, but purchased polish still costs credits. Undelivered polish refunds only its original surcharge; partial/full refunds must not exceed the original charge or use a newly changed catalog price.
- Alipay, WeChat Pay, and Stripe support membership orders and credit-pack purchases. Preserve callback signature validation, order-type routing, amount checks, and duplicate-callback safety.
- Stripe activation requires `payment_status == "paid"`; a completed checkout session is not by itself proof of payment.
- Referral rewards, signup trials, and subscription-expiry reminders also affect quota/user behavior; cover them when changing activation or user bootstrap.

### Auth And Protected Admin Deletion

Auth includes password/JWT login plus configurable Linux.do, WeChat OAuth, Google OAuth, phone codes, registration/captcha options, and SMTP/Resend email delivery. OAuth callbacks write the token through an HTML handoff to localStorage; frontend URL-token compatibility is a separate entry path. Trace `auth.py`, `auth_service.py`, `sms_service.py`, admin auth settings, and the frontend auth store together.

Admin novel deletion has a strict separate contract:

- `core/project_source.py` distinguishes trusted `user / system / ai_test` creation sources. AI-assisted content is not evidence that a project is disposable.
- Public project creation defaults to `user`; only trusted internal creation paths may assign another source. Legacy migration defaults must protect user projects.
- `admin_novel_deletion_service.py` allows only `system` and `ai_test`; unknown/user sources remain protected.
- Single and bulk deletion require two explicit “删除” confirmations and a short-lived signed ticket bound to the admin and target identities/source. Bulk deletion is atomic, limited to 1–100 projects, and rejects the entire batch if any target is protected.
- Recheck targets under lock before deletion. Preserve transactional DB deletion, then cache/vector cleanup. Never bypass this with a direct admin bulk-delete query.

## Frontend Architecture And Contracts

Stack: Vue 3, TypeScript, Vite, Naive UI, Tailwind CSS 4, and Pinia. Shared HTTP helpers in `src/api/http.ts` use fetch; do not assume every API module uses Axios.

### Boot And Routes

- `src/main.ts`: app/plugins and authentication handoff.
- `src/router/index.ts`: public/auth/admin routes, forced password-change handling, and stale-chunk recovery.
- Public routes include landing, pricing, terms/privacy, auth screens, and `/share/:token`.
- Authenticated authoring routes include `/home`, `/workspace`, `/inspiration`, `/detail/:id`, `/novel/:id`, and `/settings`; admin routes include `/admin` and `/admin/novel/:id`.
- `SharedNovelView.vue` + `api/share.ts` intentionally use a public reading API rather than authenticated request/logout behavior.
- `components/shared/NovelDetailShell.vue` holds the actual project-detail implementation reused by user/admin views, including sections, volumes, sharing, and covers.

### Writing Desk

`views/WritingDesk.vue` assembles `WDChapterRail`, `WDPlanningCanvas`, `WDWorkspace`, `WDContextRail`, `WDModelPicker`, `WDTaskCenter`, `WDOutlineTaskCard`, and review/history/version dialogs.

- Guided/professional layouts share the same underlying generation contracts.
- `utils/writingWorkflow.ts` defines the two author-facing phases: chapter planning and prose creation. Internal checks are not extra top-level creative phases.
- `useGenerationProgress.ts` and `utils/generationStages.ts` unify task/SSE/progress events; progress percentages must not move backward.
- Gateway availability probing selects background tasks or direct SSE. `useAsyncGeneration.ts` falls back from WebSocket to polling and relies on server terminal state, not guessed elapsed-time failure.
- `utils/streamInterruption.ts` reconciles disconnected streams; `budgetSkip.ts` explains skipped work; `upgradeHint.ts` and `errorHumanize.ts` distinguish access/credit issues from other failures.
- `useChapterDraft.ts` uses IndexedDB with debounced writes; a draft is durable only after transaction completion. Preserve offline recovery and explicit revision-conflict handling in `WDWorkspace.vue`.
- The optional narrative-state panel exposes coverage, facts/relationships, promises and reference roles without model calls. Context/execution receipts are bound to an immutable version; report completion is not proof that a modification was applied. Historical missing receipts stay unknown.
- `api/novel.ts` contains candidate selection, reliable saves/history/diff/restore, outlines, diagnostics, archive/rebuild, export/submission preflight, and selection transforms (`expand / rewrite / de_ai`).

Other API/state entry points: `api/model_catalog.ts`, `api/payment.ts`, `api/plans.ts`, `api/credits.ts`, `api/volumes.ts`, `api/task.ts`, `stores/auth.ts`, and `stores/novel.ts`.

### Admin And UI Styling

`AdminView.vue` is a sidebar-driven lazy component shell. Admin modules include API/provider management, LLM diagnostics, model catalog, feature gating, quality loops, skills, users, protected novel deletion, prompts, auth settings, plans, and payments.

- `Statistics.vue` includes `SystemVersionCard.vue`, backed by administrator-only `GET /api/admin/system-info` and `release_info_service.py`. Running-image metadata takes precedence over environment/development Git; deployment time is shown only for a matching image `build_id`. Never substitute build/start time or current host HEAD for a missing deployment record.
- `LLMDiagnostics.vue`, `ModelCatalogConfig.vue`, `FeatureGatingConfig.vue`, and `QualityLoopConfig.vue` reflect backend operational config, not standalone frontend flags.
- Settings includes credit history and referral rewards; pricing/checkout supports membership and credit packs.
- Prefer Naive UI and existing shared component patterns.
- `assets/main.css` contains tokens and base-layer styles. Shared `.md-*` component styles belong in `assets/m3-components.css`, imported into `layer(components)` immediately after the Tailwind import and **before** `@plugin`. The component stylesheet must not wrap itself in another `@layer`.
- Do not move shared styles into unlayered CSS: this can override Tailwind utilities. Validate source contracts with `styleContract.spec.ts` and built layers with `npm run check:css`.
- Router `onError`/`vite:preloadError` recovery and backend no-cache entry HTML jointly handle stale chunks; preserve loop prevention.

## Gateway And Production Topology

Important files: `gateway/cmd/gateway/main.go`, `internal/config/config.go`, `internal/auth/jwt.go`, `internal/middleware/middleware.go`, `internal/ratelimit/limiter.go`, `internal/proxy/proxy.go`, `internal/websocket/hub.go`, and `internal/taskdispatcher/`.

- Generic `/api` proxying uses optional JWT parsing plus rate limiting; Python still enforces endpoint auth. `/tasks` requires JWT, with additional ownership/admin checks.
- Authenticated limits and unauthenticated IP limits are separate. Keep payment callback routing/signature behavior intact.
- Dispatch uses Redis persistence, priorities, retry/backoff, leases, restart recovery, cancellation, and shared global capacity. Do not replace cross-replica leases with process-local locks.
- Worker HTTP timeouts must cover the longer blueprint/batch deadlines. Preserve permanent-error handling and metadata initialization after Redis JSON round trips.

The production Compose stack is more specific than “all traffic passes through Go”:

- Outer Nginx -> Go for ordinary `/api`, `/tasks`, and gateway `/ws`.
- The exact SSE generation route bypasses Go and goes to the app upstream with buffering disabled and a long read timeout.
- SPA traffic goes to the app upstream.
- Each app container runs internal Nginx :80 and one Uvicorn bound to 127.0.0.1:8000. Cross-container Go worker/proxy URLs must use `app:80`, not `app:8000`.
- Python and Go must share JWT and internal callback secrets. Production MySQL/Redis/Qdrant are internal services, not public host ports.
- Persist SQLite under the mounted storage volume if used; a database in the container writable layer disappears on rebuild.
- Check `deploy/nginx.conf`, `deploy/nginx.standalone.conf`, `deploy/supervisord.conf`, and Compose together when diagnosing stream cutoffs or task timeouts.

## Data And Runtime Configuration

- MySQL is the production default; SQLite is supported locally. SQLite sessions enable foreign-key enforcement.
- `db/init_db.py` and related bootstrap helpers still create/repair schema and seed defaults. Alembic is the versioned migration path; recent migrations cover revisions, volumes/world state, sharing, credit wallets, outline tasks, creative memory, skill versioning/project copies, and trusted project source.
- Check migration history and bootstrap repair together for model changes. Do not only add a new ORM field and assume existing installations gain it.
- Safety migrations `m7h8i9j0k1l2` and `n8i9j0k1l2m3` add canonical derivations/index publication and platform repair records. Existing text/history are retained. See `docs/novel-creation-improvement-implementation.md` for upgrade, repair API and budget semantics.
- Environment settings live in `core/config.py`; hot configuration uses `SystemConfig`, `AdminSetting`, and `db/system_config_defaults.py`.
- Runtime model keys include `llm.*`, `llm_fallback.*`, `llm_optimize.*` (polish), `llm_search.*`, and `llm_grader.*`, with separate embedding/rerank settings. Read actual consumers before inventing a new key.
- Capability overrides and quality-loop toggles also use runtime config. Existing configured values must not be overwritten by a default-seeding change.
- Environment groups include database, Redis, Qdrant/embedding, image generation, CORS/HTTPS, email/SMS, and worker shared secrets. Use example files and settings declarations, not a production `.env`, as documentation sources.

## Testing And Troubleshooting

Prefer the smallest focused regression that protects the changed contract. Important test groups under `backend/tests/`:

| Change | Start with |
| --- | --- |
| Generation/Agent contracts | `test_generation_contract.py`, `test_hybrid_executor_contract.py`, `test_service_first_regression_matrix.py`, `test_pipeline_orchestrator_e2e.py`, `test_agent_system_precollected_context.py` |
| Flow/planning/evidence | `test_pipeline_config_service.py`, `test_generation_policy_service.py`, `test_context_planner_service.py`, `test_evidence_budget_enforcement.py`, `test_scene_plan_integration.py`, `test_generation_quality_gate.py` |
| Manuscript safety/history | `test_m2_chapter_reliable_save.py`, `test_m3_history_and_export.py`, `test_regenerate_preserves_chapter.py`, `test_rewrite_guards.py` |
| Narrative/long-form loops | `test_p1_narrative_state.py`, `test_character_planning_context.py`, `test_character_significance.py`, `test_outline_revision.py`, `test_volume_retrospective.py`, `test_two_pass_draft.py` |
| LLM/provider/diagnostics | `test_generate_structured.py`, `test_thinking_model_compat.py`, `test_reasoning_effort_dispatch.py`, `test_responses_quality_contract.py`, `test_llm_fallback_channel.py`, `test_llm_call_telemetry.py` |
| Credits/auth/payment | `test_generation_billing.py`, `test_credit_quota.py`, `test_credit_purchased_pool.py`, `test_credit_pack_payment.py`, `test_payment_stripe.py`, `test_auth_login_methods.py` |
| Source/share/admin/skills | `test_admin_novel_deletion.py`, `test_project_creation_source_migration.py`, `test_public_share.py`, `test_versioned_skill_policy.py`, `test_writing_skill_registry_service.py` |
| Admin release information | `test_system_information.py`, `deploy/tests/test_release_metadata.py`, `SystemVersionCard.spec.ts`, `versionInformation.spec.ts` |
| Async delivery | `test_task_worker.py`, `test_task_worker_blueprint.py`, `test_outline_generation_task_service.py`, `test_generation_interrupt_cleanup.py`, `test_writer_progress_authz.py` |

Also run related service-specific tests discovered through the index. A passing orchestrator test alone does not validate all specialized services.

Frontend: run relevant Vitest specs plus type checking; include progress/stages, stream interruption, writing workflow, style contracts, payment/task API, and admin-deletion specs when touched. Playwright covers basic no-LLM smoke flows. Gateway: run `go test ./...`, especially task retry/metadata/worker timeout and config tests.

Diagnostics:

- `backend/logs/app.log`: application behavior.
- `backend/logs/llm.log`: model requests/responses.
- `backend/logs/trace.log`: generation spans and stage timing.
- Also inspect admin LLM diagnostics, usage/credit records, task state, stream payloads, writing archives, and revision metadata.

Trace the whole chain: router/ownership -> policy and billing -> planning/evidence -> prompt -> provider/flow -> quality/result -> candidate/revision persistence -> follow-up state -> transport/UI reconciliation. Prefer fixing repeated retrieval/model work or broken contracts over simply raising timeouts.

## Coding And Change Discipline

- Python: four spaces, snake_case functions/modules, PascalCase classes, async DB/service patterns, and `logging.getLogger(__name__)`.
- Preserve `# AIMETA` navigation headers, but verify their claims against executable code.
- Vue SFCs use PascalCase; TypeScript utilities/composables use camelCase. Prettier: no semicolons, single quotes, print width 100.
- Add meaningful generation spans through `utils/tracing.py` rather than unrelated timing logs.
- Keep secrets out of version control. Do not commit local storage, databases, generated reports, or dependency/build directories unless explicitly required.
- Keep commits focused; follow `feat:`, `fix:`, `refactor:`, and `docs:`. PRs should state affected areas, validation, UI screenshots where relevant, and any schema/runtime/deployment changes.
