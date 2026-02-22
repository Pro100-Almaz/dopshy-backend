# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands should be run from the `backend/` directory.

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the development server:**
```bash
uvicorn src.main:app --reload
```

**Run all tests:**
```bash
pytest
```

**Run a single test file or directory:**
```bash
pytest tests/unit_tests/
pytest tests/unit_tests/test_specific.py
```

**Code quality (must pass before commit):**
```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/
```

**Database migrations:**
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

**Start all services (Docker):**
```bash
docker compose up
```

## Architecture

### Layer Structure

```
src/
├── main.py              # FastAPI app factory, CORS, event hooks
├── api/                 # HTTP layer: routes + dependency injection
├── config/              # Environment-specific settings + startup/shutdown events
├── models/              # db/ (SQLAlchemy ORM) + schemas/ (Pydantic)
├── repository/          # Data access: BaseCRUDRepository + feature CRUDs
├── services/            # Business logic: orchestration, JWT generation, response building
├── securities/          # JWT auth, dual-layer password hashing (bcrypt→argon2)
└── utilities/           # Exceptions, formatters, message constants
```

### Request Flow

HTTP request → `api/routes/` → `services/` → `repository/crud/` → PostgreSQL

### Key Patterns

**Repository pattern**: All DB access goes through `BaseCRUDRepository` (`repository/base.py`). Feature-specific CRUDs (e.g., `repository/crud/account.py`) extend this base. Repositories are injected via `api/dependencies/repository.py` using FastAPI's `Depends()`.

**Database sessions**: Per-request async sessions from `repository/database.py` `AsyncDatabase`. Injected via `api/dependencies/session.py`. Connection pool is initialized on startup and disposed on shutdown (`config/events.py`).

**Configuration**: `config/manager.py` reads `ENVIRONMENT` env var and instantiates the correct settings class (`development.py`, `staging.py`, `production.py`). Settings are accessed globally via the `settings` singleton.

**Security**: Passwords use two-layer hashing — bcrypt (layer 1) then argon2 (layer 2). JWT tokens are issued on login and validated per request. HTTP exceptions are raised from `utilities/exceptions/http/`.

### Adding a New Endpoint

1. Add SQLAlchemy model in `models/db/`
2. Add Pydantic schemas in `models/schemas/`
3. Add CRUD class in `repository/crud/` extending `BaseCRUDRepository`
4. Add service class in `services/` — business logic, JWT, response building
5. Add service dependency function in `api/dependencies/service.py`
6. Create thin route handler in `api/routes/` — HTTP concerns and exception mapping only
7. Register router in `api/endpoints.py`

### Environment Setup

Copy `.env.example` to `.env` and configure:
- `ENVIRONMENT`: `DEV` | `STAGING` | `PROD`
- PostgreSQL credentials (`POSTGRES_*`)
- JWT settings (`JWT_SECRET_KEY`, `JWT_SUBJECT`, `JWT_TOKEN_PREFIX`)
- Hashing salt (`HASHING_SALT`)

Docker Compose exposes PostgreSQL on `5433`, Adminer on `8081`, and the backend on `8001`.

### Testing

- Tests live in `backend/tests/` with subdirectories: `unit_tests/`, `integration_tests/`, `security_tests/`, `end_to_end_tests/`
- `conftest.py` provides `backend_test_app` and `async_client` fixtures
- Coverage minimum is 63%; parallel execution is enabled via `pytest-xdist`
- `asyncio-mode=auto` — all async test functions work without explicit decorator

### Code Style

- **Black** line length: 119
- **isort** profile: black
- **mypy**: strict mode, Python 3.11
- Pre-commit hooks enforce formatting on every commit
