# Repository Guidelines

## Project Structure & Module Organization
Arboris-Novel is a full-stack project with a FastAPI backend and a Vue 3 frontend.

- `backend/app/`: core backend code, organized as routers → services → repositories → models/schemas.
- `backend/prompts/`: Markdown prompt templates loaded by backend services.
- `backend/storage/`: local SQLite/vector DB files for development.
- `frontend/src/`: UI source (`views/`, `components/`, `stores/`, `api/`, `router/`).
- `deploy/`: Docker Compose and deployment scripts.
- `docs/`: architecture and audit documentation.

Avoid committing generated artifacts (for example `frontend/node_modules/` or local `.env` files).

## Build, Test, and Development Commands
- Backend setup/run:
  - `cd backend && python3 -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
  - `uvicorn app.main:app --reload`
- Frontend setup/run:
  - `cd frontend && npm install`
  - `npm run dev` (Vite dev server)
  - `npm run build` (type-check + production build)
  - `npm run type-check` and `npm run format`
- Docker (full stack): `docker compose -f deploy/docker-compose.yml up -d --build`

## Coding Style & Naming Conventions
- Python: 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes.
- Keep routers thin; place business logic in `backend/app/services/`.
- Prefer async patterns (`async/await`) in backend services and DB code.
- Frontend: Vue SFC components in `PascalCase` (for example `ChapterWorkspace.vue`), TS utilities/composables in `camelCase`.
- Frontend formatting follows Prettier (`semi: false`, `singleQuote: true`, `printWidth: 100`).

## Testing Guidelines
- Current automated test coverage is limited; existing integration-style tests are in `backend/app/services/test_phase4_integration.py`.
- Run targeted backend tests with `pytest` (install first if needed):
  - `cd backend && pytest app/services/test_phase4_integration.py -q`
- For new features, add focused tests near the changed module and include at least one regression case.

## Commit & Pull Request Guidelines
- Follow the existing commit style seen in history: `feat:`, `fix:`, `docs:`, `refactor:` (optional scope like `feat(import): ...`).
- Keep commits small and single-purpose; use imperative subject lines.
- PRs should include: summary, impacted areas, validation steps/commands, and screenshots for UI changes.
- Link related issues and explicitly call out config or schema changes.

## Security & Configuration Tips
- Copy `backend/env.example` or root `.env.example` to `.env` and keep secrets out of git.
- Required production secrets include `SECRET_KEY`, `OPENAI_API_KEY`, and a non-default admin password.
- Verify `/api/health` after deployment and review logs in `backend/logs/` when troubleshooting.
