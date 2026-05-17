# OfficePortal — Current Architecture

**Last updated:** 2026-05-17 · **Reference for:** future contributors / Claude sessions

Snapshot of the live system. For phase status see
[PROJECT_STATUS.md](./PROJECT_STATUS.md).

---

## Monorepo layout

```
OfficePortal/
├── .git/                       single repo root
├── .github/workflows/ci.yml    backend pytest + compose-smoke (path-filtered)
├── .gitignore                  cross-workspace ignores
├── README.md                   workspace overview
├── docs/                       project-level docs (you are here)
├── backend/                    FastAPI + PostgreSQL + Alembic + Redis
├── admin-panel/                React + Vite + TypeScript admin UI
└── mobile-app/                 Flutter Dart-side scaffold
```

Each workspace has its own `.gitignore`, `README.md`, and (for backend
and admin-panel) lockfile / env example.

---

## Backend (`backend/`)

| Layer | Tech | Notes |
|---|---|---|
| HTTP | FastAPI | 26 routers mounted in `main.py`; ~123 endpoints |
| DB | PostgreSQL 18 | `is_active` flag everywhere except company (uses `deleted_at`) — actually it's the other way around, see below |
| ORM | SQLAlchemy 2 | `select()` syntax; `case()` for portable counts |
| Migrations | Alembic | Chain head: **`8d6e3b7c0a45`** (add_audit_logs) |
| Schemas | Pydantic v2 | `StrictRequestModel` base with `extra="forbid"` |
| Auth | JWT (python-jose) + Google OAuth (Authlib) | bcrypt via passlib |
| Cache / OTP | Redis 7 | env-driven host/port/db/password |
| Logging | Loguru | request-id middleware binds to `contextualize()` |
| Tests | pytest + SQLite in-memory | 151 passing; `tests/conftest.py` overrides `get_db` |
| Container | Dockerfile + docker-compose.yml | postgres + redis + migrate + app |
| CI | GitHub Actions | pytest + docker compose smoke |

### Soft-delete convention (important — has an exception)

Every model except `Company` filters on `deleted_at IS NULL` for "live"
rows. `Company` uses `is_active = True` instead. This is flagged in
`backend/API_AUDIT.md` section 7 as a maintenance trap. Migration to
`deleted_at` was deliberately deferred from Phase 1.

### Tenant scoping (RBAC)

Single source of truth: `app/core/permissions.py`. Helpers:

- `is_super_admin(actor)` — global, no company scope
- `is_office_admin(actor)` — bound to their company
- `is_any_admin(actor)` — super_admin OR office_admin
- `same_company(actor, target_company_id)` — True iff super_admin OR same
- `assert_same_company(actor, target_company_id)` — raises 403
- `assert_can_access_employee(db, employee_id, actor)` — full employee
  access rule with 404-on-not-found
- `require_admin` (dependency) — gate for admin-only endpoints
- `require_super_admin` (dependency, new in Phase 1) — gate for
  company mutations and other global-scope writes

Older modules use `is_global_admin` (from `app/crud/auth.py`) which
predates `permissions.py`. Both work; new code should use the helpers
in `permissions.py`.

### Audit log

`AuditLog` model + migration `8d6e3b7c0a45`. Covers:

- employee CUD
- leave approve/reject/delete
- salary_structure CUD
- payslip generate
- company CUD
- attendance update/delete
- holiday CUD
- leave_balance.adjust (delta + reason stored in `after._adjustment`)
- role CUD
- department CUD

`log_audit(...)` in `app/services/audit.py` is the single entry point.
Failures degrade to loguru rather than break user requests.

`password_hash` is stripped from employee snapshots so a leaked log
can't re-publish hashes.

### API response envelope

Everything follows `{status: int, message: str, data: T}` via
`ApiResponse[T]` in `app/utils/api_response.py`. The frontends mirror
this — see `admin-panel/src/api/types.ts` and
`mobile-app/lib/core/api/api_types.dart`. The food module (admin_food
+ employee_food) was the last holdout and got wrapped in Phase 1.

Errors use a different envelope produced by the exception handlers in
`main.py`: `{status: "error", code: int, message: str}`.

### Pagination

`PaginatedResponse[T]` — `{skip, limit, total, items}`. Used wherever
a list could grow unbounded. `Query(0, ge=0)` / `Query(10, ge=1, le=100)`
bounds applied across the codebase (Phase 1 hardening).

---

## Admin panel (`admin-panel/`)

| Layer | Library |
|---|---|
| Build | Vite 8 |
| Language | TypeScript (strict) |
| UI | React 19 |
| Styling | Tailwind CSS v4 via `@tailwindcss/vite` (no PostCSS config needed) |
| Routing | React Router 7 |
| HTTP | Axios — single client in `src/api/client.ts` |
| Server state | TanStack Query 5 |
| Auth storage | `localStorage` under key `officeportal.admin.access_token` |

### Folder layout

```
src/
├── api/           apiClient + ApiResponse/PaginatedResponse types
├── auth/          AuthProvider, useAuth, token helpers, types
├── components/    cross-feature UI primitives (placeholder)
├── features/      one folder per feature module (placeholder)
├── hooks/         generic React hooks (placeholder)
├── layouts/       AuthLayout (login), AdminLayout (sidebar)
├── lib/           env.ts (typed import.meta.env access)
├── pages/         LoginPage, DashboardPage, NotFoundPage, ForbiddenPage
└── routes/        AppRoutes + ProtectedRoute (with role allowlist)
```

Path alias `@/*` → `src/*` (configured in both `vite.config.ts` and
`tsconfig.app.json` — keep both aligned).

### Auth flow

1. User submits `/login` form → `POST /auth/admin/login`
2. Token from `data.data.access_token` is written to `localStorage`
3. `AuthProvider` probes `GET /auth/me` to populate `user`
4. Axios request interceptor attaches `Authorization: Bearer <token>`
5. Axios response interceptor clears the token on 401
6. `<ProtectedRoute allowedRoles={["super_admin", "office_admin"]} />`
   wraps the admin layout. Staff/employee tokens land on `/forbidden`

---

## Mobile app (`mobile-app/`)

| Layer | Library |
|---|---|
| Framework | Flutter (Material 3) |
| HTTP | Dio — single instance in `lib/core/api/api_client.dart` |
| State | Riverpod (`flutter_riverpod`) |
| Routing | go_router with auth-aware redirects |
| Secure storage | `flutter_secure_storage` (Keychain / EncryptedSharedPreferences) |
| Env | compile-time via `--dart-define-from-file=.env` |

### Critical setup gap

The Flutter scaffold contains only the **Dart side** (`lib/`,
`pubspec.yaml`, `analysis_options.yaml`, `.env.example`). The
platform-specific directories (`ios/`, `android/`, `web/`, etc.) are
NOT yet generated.

**Before the app can build or run**, someone with Flutter SDK installed
must run from `mobile-app/`:

```bash
flutter create . --project-name officeportal_mobile --org com.officeportal
```

`flutter create .` is non-destructive — it adds missing platform dirs
without touching the existing `lib/`, `pubspec.yaml`, or
`analysis_options.yaml`.

### Folder layout

```
lib/
├── app.dart                  MaterialApp.router
├── main.dart                 runApp(ProviderScope(child: OfficePortalApp()))
├── core/
│   ├── api/                  Dio client, ApiResponse<T>, PaginatedResponse<T>
│   ├── auth/                 auth state + models + token storage
│   └── env/                  --dart-define access
├── router/                   GoRouter with auth-aware redirects
├── features/
│   ├── login/login_screen.dart       roll_no + password form
│   └── dashboard/dashboard_screen.dart placeholder
└── widgets/                  cross-feature reusable widgets (placeholder)
```

### Auth flow

1. App boots → `AuthController._bootstrap()` reads token from
   `flutter_secure_storage`
2. If token exists → `GET /auth/me` populates user
3. `GoRouter.redirect` routes based on `AuthState.status`:
   loading → `/splash` · unauthenticated → `/login` · authenticated → `/dashboard`
4. Login posts to `POST /auth/employee/login` (roll number + password —
   different endpoint than admin login)
5. Dio interceptor attaches `Bearer` token; 401 clears storage; router
   redirects back to `/login`

---

## CI (`.github/workflows/ci.yml`)

Single workflow at the repo root. Path filter: `backend/**` +
the workflow itself. Two jobs:

```
jobs:
  test:               pytest -v --tb=short
  compose-smoke:      docker compose up --wait + curl /health
```

Both run with `defaults.run.working-directory: backend` so commands
match what a contributor sees inside that workspace.

admin-panel and mobile-app workflows haven't been added yet — drop them
in alongside the backend one when their first builds need verification.

---

## Important technical decisions

### Backend
1. **Single working branch (`chore/env-example`) + `main`**. No
   per-feature branches per saved feedback. PRs are optional;
   fast-forward merges to main are the norm.
2. **JWT stateless tokens** with no server-side revocation. Logout is
   a stub; refresh tokens are Phase 3 work.
3. **Audit-on-the-same-transaction**. `log_audit` adds rows to the
   caller's session; commits or rolls back atomically with the main
   write. Audit failures degrade to loguru, never break the user
   request.
4. **`assert_can_access_employee` is the canonical employee gate** —
   does the 404 (cross-tenant) / 403 (role) / 404 (not-found)
   classification for every employee-keyed endpoint.
5. **Soft-delete via `deleted_at`** everywhere except `Company`.

### Admin panel
1. **localStorage for JWT** (XSS exposure accepted because refresh
   tokens land in Phase 3). When refresh tokens ship, move the refresh
   token to an HttpOnly cookie and keep the access token in memory.
2. **Single axios client** with the Bearer interceptor. Don't import
   axios directly in feature code — always go through `@/api/client`.
3. **TanStack Query for ALL server state**. Don't store backend data
   in React state or Context. Auth state is the exception (lives in
   `AuthContext` because the router redirect depends on it
   synchronously).
4. **Path alias `@/*` for `src/*`** — no deep relative imports.

### Mobile
1. **Compile-time env via `--dart-define-from-file=.env`**. No runtime
   `.env` file shipped in the bundle. Mirrors what staging/production
   CI will inject.
2. **flutter_secure_storage** (not SharedPreferences) for tokens. Real
   at-rest encryption.
3. **go_router with redirect-on-auth-state** rather than imperative
   `Navigator.push` flows. Auth changes propagate to the router via
   a Riverpod `ChangeNotifier` bridge.
4. **Mobile uses `/auth/employee/login` (roll number)**, admin uses
   `/auth/admin/login` (email). Different endpoints.

---

## Deferred work (Phase 3 backlog)

Documented in `backend/API_AUDIT.md` (section 7 + deferred items):

- Refresh tokens / real `/auth/logout` revocation
- Notification system + push token registration
- TDS slabs in payroll
- Mid-month joiners + half-day attendance refinement
- MFA
- Leave carry-forward + dedicated `LeaveBalanceAdjustment` table
- `net >= 0` clamp policy
- Unpaid LeaveType
- "Alternate Saturday" / week-number weekly pattern
- Real per-company hostel scoping (vs the "any admin" interpretation)
- Pydantic `class Config` → `ConfigDict` migration
- Profile photo upload (Phase 1 deferral — needs storage-backend decision)
- Soft-delete consistency on `companies` (Phase 1 deferral)
