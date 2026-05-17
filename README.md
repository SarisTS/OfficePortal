# OfficePortal

HRMS monorepo: FastAPI backend + React admin panel + Flutter mobile app.

## Layout

```
OfficePortal/
├── backend/         FastAPI + PostgreSQL + Alembic — see backend/Readme.md
├── admin-panel/     React + Vite + TypeScript admin UI (Phase 2 scaffold)
├── mobile-app/      Flutter employee app (Phase 2 scaffold)
├── docs/            Cross-workspace design notes
├── .github/         CI workflows (path-filtered per workspace)
├── .gitignore       Monorepo-level ignores; each workspace has its own
└── README.md        This file
```

## Workspaces

| Workspace | Stack | Status |
|---|---|---|
| [backend](./backend/) | FastAPI · PostgreSQL · SQLAlchemy 2 · Alembic · Redis | Stable (Phase 1 audit + stabilization complete — see [`backend/API_AUDIT.md`](./backend/API_AUDIT.md)) |
| [admin-panel](./admin-panel/) | React · Vite · TypeScript · Tailwind · React Router · Axios · TanStack Query | Scaffold in progress (Phase 2) |
| [mobile-app](./mobile-app/) | Flutter · Dio · flutter_secure_storage | Scaffold in progress (Phase 2) |

## Common commands

```bash
# Backend (from repo root)
cd backend
docker compose up --build        # full stack: db + redis + migrations + api on :8000
pytest -v                        # backend test suite

# Admin panel (once scaffolded)
cd admin-panel
npm install
npm run dev                      # vite dev server on :5173

# Mobile app (once scaffolded)
cd mobile-app
flutter pub get
flutter run                      # device / simulator
```

## CI

`.github/workflows/ci.yml` runs the backend pytest + docker compose smoke
on any push that touches `backend/**` or the workflow itself.
admin-panel and mobile-app workflows land alongside their scaffolds.

## Phase 2 status

Currently restructuring from the single-folder backend repo into this
monorepo layout. Backend stays runnable through every step. Phase 2
tracking lives in [`docs/`](./docs/) — design notes and ADRs appear
there as decisions are made.
