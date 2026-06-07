# Arboris Novel - AI Writing Platform

## Overview
An AI-powered writing assistant platform for Chinese web novel authors. Features a custom advanced Multi-Agent architecture for maintaining narrative consistency, managing world-settings, and generating high-quality drafts.

## Architecture
- **Backend**: Python 3.12 + FastAPI (port 8000)
- **Frontend**: Vue 3 + Vite + TypeScript (port 5000)
- **Database**: PostgreSQL (Replit managed via DATABASE_URL secret)
- **AI/LLM**: OpenAI-compatible API via configurable base URL

## Project Structure
- `backend/` - FastAPI application
  - `app/agents/` - Multi-agent system implementation
  - `app/services/` - Business logic (RAG, prompt assembly, etc.)
  - `app/api/` - REST API endpoints
  - `app/models/` - SQLAlchemy models
  - `app/schemas/` - Pydantic schemas
  - `prompts/` - Markdown prompt templates
- `frontend/` - Vue 3 application
  - `src/views/` - Main pages (Writing Desk, Inspiration Mode, Novel Workspace)
  - `src/components/` - UI components
  - `src/stores/` - Pinia state management
- `gateway/` - Go-based LLM Gateway (optional, not used in dev)

## Public Pages
- `/landing` - Professional public homepage (no auth required), dynamically shows pricing plans from backend
- `/pricing` - Detailed pricing page (no auth required)
- `/login`, `/register` - Auth pages

## Admin Management Pages (requires auth + admin)
- `/admin?tab=membership_plans` - Manage subscription plans (CRUD, saved to `plans` table)
- `/admin?tab=payment_channels` - Configure Stripe/Alipay/WeChat payment channels
- `/admin?tab=payment_records` - View payment records with filters and CSV export

## Key Configuration (Environment Variables)
- `DATABASE_URL` - Replit-managed PostgreSQL (set automatically)
- `SECRET_KEY` - JWT signing key (set in .replit userenv)
- `DB_PROVIDER` - Set to "sqlite" but DATABASE_URL takes precedence
- `OPENAI_API_KEY` - Required for LLM features (set as secret)
- `CORS_ORIGINS` - Set to "*" for development

## Workflows
- **Backend**: `cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- **Start application** (Frontend): `cd frontend && npm run dev` (port 5000)
- **Project**: Runs both in parallel

## Database
- Uses Replit's built-in PostgreSQL via `DATABASE_URL` secret
- Schema auto-created via SQLAlchemy `create_all` on startup
- Default admin: username=admin, password=ChangeMe123!
- Prompts auto-synced from `backend/prompts/*.md` on startup

## Dependencies
- Python: fastapi, uvicorn, sqlalchemy, asyncpg, aiosqlite, pydantic, openai, redis, qdrant-client, celery, mem0ai
- Node: vue, vite, naive-ui, pinia, tailwindcss, vis-network, chart.js

## Notes
- Frontend proxies `/api/*` requests to backend at `http://127.0.0.1:8000`
- Qdrant vector store is optional (disabled when QDRANT_HOST is empty)
- Redis optional for Celery tasks (REDIS_URL defaults to localhost:6379)
- LLM features require OPENAI_API_KEY secret to be configured
