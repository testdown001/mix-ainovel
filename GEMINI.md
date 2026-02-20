# Arboris Novel Project Context

## Project Overview
Arboris Novel is an AI-powered novel writing assistant designed to help authors organize storylines, manage characters, and generate content. It features a full-stack architecture with a Vue.js frontend and a FastAPI backend, utilizing Large Language Models (LLMs) for creative assistance.

## Architecture

### Backend (`backend/`)
*   **Framework:** FastAPI (Python 3.10+)
*   **Database ORM:** SQLAlchemy (Async)
*   **Database Support:** SQLite (default), MySQL (via `asyncmy`)
*   **AI Integration:** OpenAI API compatible client (supports OpenAI, Claude, etc.)
*   **Task Queue:** Celery (implied by configuration)
*   **Key Libraries:** `pydantic`, `alembic`, `uvicorn`, `python-jose` (JWT)

### Frontend (`frontend/`)
*   **Framework:** Vue.js 3
*   **Build Tool:** Vite
*   **Styling:** TailwindCSS v4, Naive UI
*   **State Management:** Pinia
*   **Routing:** Vue Router
*   **Language:** TypeScript

### Infrastructure (`deploy/`)
*   **Containerization:** Docker & Docker Compose
*   **Web Server:** Nginx (production)

## Key Directories & Files

### Root
*   `prompts/`: Markdown files containing system prompts for various AI tasks (e.g., `chapter_plan.md`, `character_dna_guide.md`). Crucial for understanding AI behavior.
*   `deploy/`: Deployment configurations (`docker-compose.yml`, `Dockerfile`).
*   `docs/`: Project documentation.

### Backend (`backend/app/`)
*   `main.py`: Application entry point, lifespan management, and middleware setup.
*   `api/`: API route definitions.
*   `core/config.py`: Application configuration settings (env vars).
*   `db/`: Database connection (`session.py`) and migrations (`alembic`).
*   `models/`: SQLAlchemy database models. Key models include:
    *   `novel.py`: Core novel data.
    *   `chapter_blueprint.py`: Story outlining.
    *   `entity_registry.py` & `faction.py`: World-building elements.
    *   `writer_persona.py`: AI writing style configuration.
*   `services/`: Business logic, including `prompt_service.py` and likely `llm_service.py`.

### Frontend (`frontend/src/`)
*   `App.vue`: Root component.
*   `main.ts`: Entry point.
*   `router/index.ts`: Client-side routing.
*   `stores/`: Pinia state stores.
*   `views/`: Page-level components.
*   `components/`: Reusable UI components.

## Development Workflow

### Prerequisites
*   Python 3.10+
*   Node.js 18+
*   Docker (optional, for full stack run)

### Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Run migrations (if applicable)
# alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Docker Quickstart
```bash
cp .env.example .env
# Edit .env to set OPENAI_API_KEY and SECRET_KEY
docker compose up -d
```

## Conventions
*   **Environment Variables:** Managed via `.env` file (see `.env.example`).
*   **API Style:** RESTful API with Pydantic models for request/response validation.
*   **Async/Await:** Heavy use of Python `async/await` for database and AI I/O.
*   **Styling:** Utility-first CSS using Tailwind.
*   **AI Prompts:** Managed as external Markdown files in `prompts/` rather than hardcoded strings.

## Common Issues
*   **Database:** SQLite is default. For MySQL, ensure drivers (`asyncmy`) are installed and connection strings in `.env` are correct.
*   **AI Rate Limits:** Check `backend/logs/llm.log` if AI responses fail.
