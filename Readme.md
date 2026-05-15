# Office Portal — Backend

A multi-tenant HRMS backend: attendance with geo-fencing, shift assignments,
leave management, hostels, daily food selection, and per-company RBAC.
Built on FastAPI + PostgreSQL + SQLAlchemy.

---

## Features

- **Authentication** — admin (email/password) and employee (mobile + OTP)
  login flows. JWT bearer tokens, Google OAuth for admins.
- **Role-based access control** — `super_admin`, `office_admin`, `staff`,
  `employee`. Per-company tenant scoping enforced in CRUD + service layers.
- **Attendance** — geo-fenced check-in/check-out, configurable shift windows
  (early-buffer, late grace, night-shift handling), manual marking by admins.
- **Shift management** — shift definitions, assignment history, change with
  overlap detection.
- **Leave** — request, approve/reject, overlap prevention, auto-apply to
  attendance on approval.
- **Hostels** — per-company directory with geographic-location linkage.
- **Food** — daily menu management + employee selection with meal-time cutoffs.
- **Observability** — per-request UUID, structured (JSON) logging on demand,
  `/health` probe for liveness checks.

---

## Tech Stack

- **Framework**: FastAPI, Starlette
- **DB**: PostgreSQL, SQLAlchemy 2.0, Alembic
- **Auth**: python-jose (JWT), passlib + bcrypt, Authlib (Google OAuth)
- **Cache**: Redis (OTP storage)
- **Config**: pydantic, pydantic-settings
- **Logging**: loguru (text + JSON modes)
- **Timezone**: pytz (configurable via `TIMEZONE` env var; default
  `Asia/Kolkata`)
- **Tests**: pytest with an in-memory SQLite fixture

---

## Getting Started

### 1. Clone

```bash
git clone https://github.com/SarisTS/OfficePortal.git
cd OfficePortal
```

### 2. Virtual env and dependencies

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

Add `pip install -r requirements-dev.txt` if you want to run the test suite.

### 3. Configure

```bash
cp .env.example .env
```

Fill in the real values. Generate a strong `SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 4. Database

Create the Postgres database referenced in `DATABASE_URL`, then apply
migrations:

```bash
alembic upgrade head
alembic current     # expect: <latest revision> (head)
```

### 5. Run

```bash
uvicorn main:app --reload
```

Interactive API docs: <http://localhost:8000/docs>
(FastAPI auto-generates Swagger UI from the routers.)

Liveness/readiness probe: <http://localhost:8000/health>
(returns DB + Redis status; DB failure → 503, Redis is best-effort.)

---

## Tests

```bash
pip install -r requirements-dev.txt   # one-time
pytest
```

The suite uses an in-memory SQLite database via `tests/conftest.py`, so
no real Postgres is required. SQLite-specific caveats (partial unique
indexes, row locking, native ENUM types) are documented in the
conftest docstring — these checks live in production only.

---

## Project Layout

```
OfficePortal/
├── app/
│   ├── core/           settings, security, permissions, oauth, logger, redis
│   ├── database/       engine, session factory, get_db, with_transaction
│   ├── models/         SQLAlchemy ORM models
│   ├── schemas/        Pydantic request/response models (StrictRequestModel base)
│   ├── crud/           DB access functions (one module per resource)
│   ├── services/       Business logic (attendance, shift assignment, etc.)
│   ├── routers/        FastAPI routers
│   └── utils/          api_response wrapper, distance/hash helpers
├── migrations/         Alembic
├── tests/              pytest suite
├── main.py             FastAPI app, middleware, exception handlers
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

---

## Author

Sarish — Software Developer
