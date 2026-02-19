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
# SQLite (default, simplest)
cd deploy && cp ../.env.example .env  # edit .env
docker compose up -d

# MySQL
DB_PROVIDER=mysql docker compose --profile mysql up -d
```

Health check: `GET /api/health`

## Architecture

### Backend (`backend/app/`)

Layered architecture: **Routers → Services → Repositories → Models**

- `main.py` — FastAPI entry, lifespan (DB init + prompt preload), CORS, router registration
- `api/routers/` — REST endpoints. Key routers: `writer.py` (chapter generation, 49KB), `novels.py` (project management), `auth.py` (JWT auth), `admin.py` (admin panel)
- `services/` — 54 service files (~17K lines). Core services:
  - `pipeline_orchestrator.py` (46KB) — orchestrates the full writing pipeline: context assembly → RAG retrieval → LLM generation → review
  - `llm_service.py` — unified LLM calling (OpenAI-compatible + Ollama), embedding generation
  - `novel_service.py` — novel CRUD and business logic
  - `blueprint_service.py` — chapter outline/blueprint management
  - `vector_store_service.py` — libsql vector DB operations (chunk/summary storage and retrieval)
  - `knowledge_retrieval_service.py` — RAG retrieval engine
  - `import_service.py` — existing novel import and parsing
- `models/` — SQLAlchemy ORM models (18 tables): Novel, Chapter, ChapterVersion, Character, Faction, Constitution, Foreshadowing, MemoryLayer, WriterPersona, LLMConfig, etc.
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

- **SQLite** (default): zero config, file at `storage/arboris.db`
- **MySQL 8.0+**: for production, async via `asyncmy`
- **libsql** (optional): vector DB for RAG at `storage/rag_vectors.db`, stores `rag_chunks` (text embeddings) and `rag_summaries` (chapter summary embeddings)
- All DB access is async (aiosqlite / asyncmy). Session factory: `db/session.py` → `AsyncSessionLocal`
- No Alembic migrations are actively used; tables are created via `init_db()` at startup

### RAG Pipeline

Chapter generation retrieves context from the vector store:
1. Current chapter goals → query embedding via configured embedding model
2. Vector similarity search: top-K chunks (default 5) + top-K summaries (default 3)
3. Retrieved content injected into LLM prompt alongside blueprint + previous chapter summaries
4. After chapter finalization: text split (LangChain `RecursiveCharacterTextSplitter`, 480 chars/120 overlap) → embed → store in libsql

### Key Env Variables

Required: `SECRET_KEY`, `OPENAI_API_KEY`, `ADMIN_DEFAULT_PASSWORD`

LLM config: `OPENAI_API_BASE_URL`, `OPENAI_MODEL_NAME`, `WRITER_CHAPTER_VERSION_COUNT`

Embedding: `EMBEDDING_PROVIDER` (openai|ollama), `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`

Vector DB: `VECTOR_DB_URL`, `VECTOR_TOP_K_CHUNKS`, `VECTOR_TOP_K_SUMMARIES`, `VECTOR_CHUNK_SIZE`

DB: `DB_PROVIDER` (sqlite|mysql), `SQLITE_DB_PATH`, `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`

## Code Conventions

- Backend uses `# AIMETA` comment headers on key files for AI navigation metadata
- All backend services are async; use `async/await` throughout
- LLM interactions go through `llm_service.py` — never call OpenAI/Ollama directly from routers
- Prompt templates live in `backend/prompts/*.md` and are synced to DB on startup; edit the `.md` files, not DB records directly
- Frontend uses Naive UI component library — prefer its components over custom implementations
- Frontend styling: TailwindCSS 4 utility classes (PostCSS integration, not `@tailwind` directives)
- Node engine requirement: `^20.19.0 || >=22.12.0`
