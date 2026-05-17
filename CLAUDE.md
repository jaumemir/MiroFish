# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MiroFish is an AI-powered multi-agent simulation platform. It extracts entities from user-provided documents (PDF/MD/TXT), builds a knowledge graph (via Zep Cloud or Graphiti+Neo4j), generates agent personas, runs social interaction simulations (via OASIS/CAMEL-AI), and produces analytical reports. The platform has multi-user support with JWT authentication and role-based access control (admin / user).

## Commands

### Setup
```bash
cp .env.example .env          # Configure API keys before first run
npm run setup:all             # Install Node + Python dependencies (root, frontend, backend)
npm run setup                 # Node deps only
npm run setup:backend         # Python deps only (uv venv)
uv run python backend/scripts/init_system.py  # Init DB + create admin user (first run only)
```

### Development
```bash
npm run dev                   # Start both frontend (port 3000) & backend (port 5001) concurrently
npm run frontend              # Frontend only
npm run backend               # Backend only (uv run python run.py)
```

### Build
```bash
npm run build                 # Vite production build of frontend
```

### Testing
```bash
pytest                        # Run Python tests (pytest + pytest-asyncio available in venv)
```

Python 3.11–3.12 required (strict constraint). Node 18+ required.

## Architecture

### Overview
Full-stack monorepo: **Vue 3 SPA** (frontend, port 3000) + **Flask API** (backend, port 5001). Vite proxies all `/api/*` requests to the backend.

### 5-Step Workflow Pipeline
1. **Graph Build** — Upload seed documents → ontology generation → entity/relationship extraction via LLM → knowledge graph (Zep Cloud or Graphiti+Neo4j)
2. **Environment Setup** — Agent persona generation (OASIS profiles) from the graph; each agent gets stance (supportive/opposing/neutral/observer) based on entity context
3. **Simulation** — OASIS multi-agent simulation (Info Plaza / Topic Community platforms) run as a subprocess
4. **Report** — ReportAgent (LLM with tool calling) analyzes simulation output; max 5 tool calls, 2 reflection rounds
5. **Interaction** — Live chat with simulated agents

### Authentication & Users
- JWT Bearer tokens (flask-jwt-extended). Access: 8h, Refresh: 7d.
- Two roles: **admin** (full platform access) and **user** (owns their own projects).
- User lifecycle: `pending` (invited, no password) → `active` → `disabled` (soft-deleted).
- Admin routes: `GET/POST /api/users/`, `PATCH/DELETE /api/users/<id>`, `/api/admin/config`, `/api/admin/executions`.
- Ownership enforced via `@require_project_owner` decorator (admin bypasses it).

### Key Backend Patterns
- **`models/db_models.py`** — SQLAlchemy models: `UserModel`, `ProjectModel`, `GraphModel`, `SimulationModel`, `ReportModel`, `TaskModel`, `SystemConfigModel`, etc. SQLite by default; configurable via `DATABASE_URL`.
- **`models/task.py`** — `TaskManager` singleton. Async task tracking (PENDING → PROCESSING → COMPLETED|FAILED). Frontend polls `GET /api/graph/task/{taskId}`.
- **`services/simulation_runner.py`** — Spawns OASIS as a subprocess. Communicates via IPC files at `/tmp/mirofish_sim_{id}_*.json`. Atexit cleanup registered.
- **`services/report_agent.py`** — Multi-turn LLM agent with tool use. Max 5 tool calls, 2 reflection rounds.
- **`utils/locale.py`** — Thread-local locale storage. Reads `Accept-Language` header from requests; falls back to thread-local for background workers.
- **`graph/factory.py`** — Singleton that instantiates `ZepBackend` or `GraphitiBackend` based on `GRAPH_BACKEND` env var.

### Key Frontend Patterns
- **`api/index.js`** — Axios instance with retry (`requestWithRetry`, 3 attempts, exponential backoff) and response interceptor. Auto-injects `Accept-Language` and `Authorization: Bearer` headers.
- Views are self-contained; no shared state beyond `projectId` in the URL route.

### i18n
Translation files at `/locales/{en,ca,es}.json` are shared by both frontend and backend. The frontend uses `vue-i18n` v11 with `localStorage` persistence. The backend reads the `Accept-Language` header. `/locales/languages.json` also contains per-language LLM prompt instructions (to force LLM output language).

### Configuration (`backend/app/config.py`)
Key environment variables (from `.env`):
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME` — main LLM, any OpenAI-compatible API
- `LLM_PROVIDER=gemini` — optional, auto-configures Google AI Studio endpoint
- `GRAPH_BACKEND` — `zep` (default, requires `ZEP_API_KEY`) or `graphiti` (requires `NEO4J_*` vars)
- `LLM_EMBED_*`, `LLM_SMALL_*` — optional dedicated embedding/lightweight models (used by Graphiti)
- `LLM_BOOST_API_KEY/BASE_URL/MODEL_NAME` — optional faster LLM for OASIS simulation
- `JWT_SECRET_KEY` — required in production
- `ADMIN_EMAIL`, `ADMIN_PASSWORD` — used by `init_system.py` to create the first admin
- `DATABASE_URL` — SQLite by default (`sqlite:///mirofish_dev.db`)
- `STORAGE_TYPE` — `local` (default) or `azure` (requires `AZURE_STORAGE_CONNECTION_STRING`)
- `ACS_ENDPOINT`, `ACS_ACCESS_KEY`, `ACS_SENDER_ADDRESS` — Azure Communication Services for email

## Git Remotes
- `origin` — this fork: `https://github.com/jaumemir/MiroFish`
- `upstream` — original project: `https://github.com/666ghj/MiroFish`

To cherry-pick from upstream branches or PRs:
```bash
git fetch upstream
git cherry-pick <commit-sha>
# or: git merge upstream/<branch-name>
```
