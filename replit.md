# Arboris-Novel

An AI-assisted writing platform designed for Chinese web novel authors. Functions as an "AI editorial team" using a multi-agent architecture called "Three Provinces and Six Ministries" (三省六部).

## Project Structure

```
/
├── backend/          # FastAPI Python backend
│   ├── app/         # Application code
│   │   ├── api/     # API routers/endpoints
│   │   ├── core/    # Config, security, middleware
│   │   ├── db/      # Database session, init, models
│   │   ├── models/  # SQLAlchemy ORM models
│   │   ├── schemas/ # Pydantic schemas
│   │   ├── services/# Business logic services
│   │   └── tasks/   # Celery background tasks
│   ├── prompts/     # Prompt template markdown files
│   └── requirements.txt
├── frontend/         # Vue 3 + Vite frontend
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   └── stores/
│   └── package.json
└── gateway/         # Go-based LLM API gateway (not used in dev)
```

## Tech Stack

- **Frontend**: Vue 3, TypeScript, Vite, Naive UI, TailwindCSS 4, Pinia
- **Backend**: Python FastAPI, SQLAlchemy (async), asyncpg (PostgreSQL)
- **Database**: PostgreSQL (Replit managed via DATABASE_URL)
- **Cache**: Redis (optional, cache service degrades gracefully)
- **LLM**: OpenAI-compatible API

## Workflows

- **Start application** (port 5000): Vue 3 frontend dev server
- **Backend** (port 8000): FastAPI backend server

## Database

Uses Replit's built-in PostgreSQL database via `DATABASE_URL` environment variable. The backend auto-creates all tables on startup via SQLAlchemy `create_all`.

## Environment Variables

Key variables set in Replit Secrets/Env:
- `SECRET_KEY`: JWT signing key
- `ADMIN_DEFAULT_PASSWORD`: Initial admin password (ChangeMe123!)
- `ADMIN_DEFAULT_USERNAME`: admin
- `DATABASE_URL`: Auto-provided by Replit PostgreSQL
- `CORS_ORIGINS`: Set to `*` for development

## Modifications from Original

1. Added PostgreSQL support (project originally required MySQL)
   - `backend/app/core/config.py`: Added asyncpg driver normalization, sslmode->ssl conversion, sqlite support
   - `backend/app/db/session.py`: Updated to detect db type from URI
   - `backend/app/db/init_db.py`: Skip MySQL-specific operations for PostgreSQL/SQLite

2. Frontend configured for Replit proxy:
   - `frontend/vite.config.ts`: Set host to 0.0.0.0, port to 5000, allowedHosts: true

## Default Admin Credentials

- Username: admin
- Password: ChangeMe123!

## Notes

- Redis/Celery are optional - the cache service handles Redis unavailability gracefully
- Qdrant vector database is disabled by default (QDRANT_HOST not set)
- LLM features require an `OPENAI_API_KEY` to be configured in the admin panel
