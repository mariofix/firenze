# Copilot instructions for `zvn-firenze`

## Build, run, test, and lint commands

Environment setup (from `dev-instructions.md`):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p logs
```

Apply DB migrations:

```bash
alembic upgrade head
```

Run the API locally:

```bash
fastapi dev run.py --port 9002
```

Run with the production server shape used in docs:

```bash
gunicorn run:app -k uvicorn.workers.UvicornWorker --workers 1
```

Run tests:

```bash
pytest
```

Run a single test file:

```bash
pytest tests/test_credit_service.py
```

Run a single test case:

```bash
pytest tests/test_did_service.py::TestResolveDid::test_returns_full_config_when_found
```

Lint/format tools used in this repo (`pyproject.toml` dev deps):

```bash
ruff check .
black .
isort .
```

## High-level architecture

- **Entry points**
  - API: `run.py` -> `firenze.create_app()`
  - CLI: `cli.py` / `firenze` script -> `firenze.cli:cli`
- **App composition (`firenze/__init__.py`)**
  - FastAPI app factory with middleware for CORS, sessions, trusted hosts, debug toolbar, and `InternalOnlyMiddleware` for AGI paths.
  - Routers mounted from:
    - `firenze.api.agi` (`/agi/*`, dialplan-facing)
    - `firenze.auth` (auth endpoints)
    - `firenze.api.payments` and `firenze.api.public` (`/api/v1/*`)
  - SQLAdmin is mounted with `FirenzeAdmin`.
- **Core layers**
  - Models: `firenze/models/*` (SQLAlchemy 2.0 style).
  - Business logic: `firenze/services/*` (DID resolution, credit rules, operators, clients, call lifecycle, payments).
  - API modules are mostly thin adapters over service functions and response-shape contracts.
- **State model**
  - MySQL is authoritative (`firenze/database.py`).
  - Redis/Valkey is a hot cache mirror (`firenze/redis/*`) for operator and active-call state (`firenze:operator:{number}`, `firenze:call:{service}:{ani}`).
- **Telephony integration context**
  - Project is in AGI -> HTTP migration for Asterisk.
  - Current/target dialplan context and rollout status are tracked in `tasks.md`, `new-architecture.md`, and `tech.md`.

## Key conventions in this codebase

- **AGI response contract is strict and dialplan-oriented**: `/agi/*` returns flat JSON with legacy field names (e.g., `siguiente`, `servicio`, `clientid`, `segundos`) specifically for Asterisk `CURL()` + `JSON_DECODE()`.
- **Security split by surface**:
  - `/agi/*` endpoints are internal-only (network-gated by `InternalOnlyMiddleware` and `AGI_ALLOWED_NETWORKS`) and intentionally not JWT-based.
  - Storefront/admin APIs under `/api/v1/*` use auth/scopes.
- **Operator selection is intentionally two-step**:
  - Info endpoints (`/agi/operators/by-option/*`, `/by-ani/*`) do lookup only.
  - Real claim happens in `/agi/operators/select` (atomic behavior in service layer).
- **Client identity is service-scoped**:
  - Unified `Client` model keyed by service/client pairing plus `ClientAni` child mapping for ANI auth flows.
- **Keep migration context in sync**:
  - Treat `tasks.md` as rollout status, `new-architecture.md` as big-picture rationale, and `tech.md` as implementation contract/reference.
- **Project-specific assistant guidance exists in `CLAUDE.md`**:
  - For substantial tasks, align with its migration-focused workflow and branch conventions (`copilot/*`, with `new-architecture` as the documented exception branch).
