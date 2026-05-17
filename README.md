# OfficePortal

HRMS monorepo: FastAPI backend + React admin panel + Flutter mobile app.

## Layout

```
OfficePortal/
├── backend/             FastAPI · PostgreSQL · Alembic · Redis
├── admin-panel/         React · Vite · TypeScript admin UI
├── mobile-app/          Flutter employee app
├── docs/                Cross-workspace design notes + monorepo guide
├── .github/             CI workflows (path-filtered per workspace)
├── docker-compose.yml   Local dev stack (db + redis + migrate + app)
├── CLAUDE.md            Monorepo-wide rules for Claude sessions
├── .gitignore           Cross-cutting ignores only; each workspace has its own
└── README.md            This file
```

## Workspaces

| Workspace | Stack | Status |
|---|---|---|
| [backend](./backend/) | FastAPI · PostgreSQL · SQLAlchemy 2 · Alembic · Redis | Stable (Phase 1 audit complete — see [`backend/API_AUDIT.md`](./backend/API_AUDIT.md)) |
| [admin-panel](./admin-panel/) | React · Vite · TypeScript · Tailwind · React Router · Axios · TanStack Query | Scaffold (Phase 2) |
| [mobile-app](./mobile-app/) | Flutter · Dio · Riverpod · flutter_secure_storage | Scaffold (Phase 2) |

## Common commands

```bash
# Full local stack (from repo root): postgres + redis + migrations + api
docker compose up --build           # api on http://localhost:8000
docker compose down                 # stop, keep volume
docker compose down -v              # stop, drop the db volume

# Backend tests (from backend/)
cd backend
pytest -v

# Admin panel (from admin-panel/)
cd admin-panel
npm install
npm run dev                         # http://localhost:5173

# Mobile app (from mobile-app/, after one-time `flutter create .`)
cd mobile-app
flutter pub get
flutter run --dart-define-from-file=.env
```

See [`docs/MONOREPO_GUIDE.md`](./docs/MONOREPO_GUIDE.md) for the full
startup / docker / CI / env reference.

## CI

`.github/workflows/ci.yml` runs the backend pytest suite + a docker
compose smoke test on any push that touches `backend/**`,
`docker-compose.yml`, or the workflow itself. admin-panel and
mobile-app workflows land alongside their first non-scaffold commits.

## Phase status

See [`docs/PROJECT_STATUS.md`](./docs/PROJECT_STATUS.md) for the full
phase tracker and recommended next steps.
