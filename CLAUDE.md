# OfficePortal — Claude Code rules

Monorepo-wide guidance for any Claude session working in this repo.
Workspace-specific files (`backend/`, `admin-panel/`, `mobile-app/`)
inherit these rules.

---

## Repository shape

OfficePortal is a three-workspace monorepo:

| Workspace | Stack | Owns |
|---|---|---|
| `backend/` | FastAPI · PostgreSQL · SQLAlchemy 2 · Alembic · Redis | API, schema, migrations, business logic |
| `admin-panel/` | Vite · React 19 · TypeScript · Tailwind v4 · TanStack Query | Admin web UI (super_admin / office_admin) |
| `mobile-app/` | Flutter · Dio · Riverpod · go_router | Employee mobile app |

Root-level assets (compose, CI, docs, .gitignore) orchestrate the
monorepo. Per-workspace assets (Dockerfile, package.json, pubspec.yaml,
.env.example) stay in their workspace.

See `docs/MONOREPO_GUIDE.md` for paths, startup commands, and CI/env
conventions.

---

## Branching

- **Single working branch**: `chore/env-example` → fast-forward merged
  to `main`, both pushed. No per-feature branches.
- Never modify `main` directly via destructive operations (force-push,
  reset). Always merge from the working branch.
- Never skip hooks (`--no-verify`) or bypass signing unless explicitly
  asked.

---

## Cross-workspace rules

- Before changing anything: read the existing code, understand the
  models / services / APIs / dependencies, and identify weaknesses.
- Prefer stabilising existing code over adding new features.
- Preserve backward compatibility unless the user has authorised a
  break.
- Never delete existing functionality without explicit instruction.
- Match scope to the request: a bug fix is not an invitation to
  refactor, and a refactor is not a feature.
- Don't add features, abstractions, or error handling for cases that
  can't happen. Trust internal code; only validate at boundaries.
- Default to no comments. Add one only when WHY is non-obvious.
- For UI / frontend changes, run the dev server and exercise the
  feature in a browser before reporting it done. Type-checks and test
  suites prove correctness of code, not of feature behaviour.

---

## Backend (`backend/`)

### Code quality
- Clean architecture: routers → services → CRUD → models. Don't put
  business logic in routers or in CRUD.
- No duplicated logic — extract to `app/services/` or `app/utils/`.
- All listing APIs paginate via `PaginatedResponse[T]`.
- All responses use the `ApiResponse[T]` envelope.
- All Pydantic request bodies inherit `StrictRequestModel` (rejects
  unknown keys).
- Optimise DB queries: avoid N+1, use eager loading where helpful,
  suggest indexes when they'd materially help.
- Use transactions where needed (`app/database/session.py:with_transaction`).

### Database
- Schema improvements go through Alembic migrations. Explain why.
- Avoid destructive migrations unless necessary.
- Add `created_at` / `updated_at` / `deleted_at` / `created_by` /
  `updated_by` columns when introducing a model.
- Soft delete via `deleted_at IS NULL` everywhere except `Company`
  (which uses `is_active = True` — flagged as a maintenance trap,
  fix deferred from Phase 1).

### Security
- All tenant-scoped endpoints use the helpers in
  `app/core/permissions.py` (`assert_same_company`, `require_admin`,
  `require_super_admin`, `assert_can_access_employee`).
- Use `same_company` checks before exposing cross-tenant data.
- Sanitise input via `StrictRequestModel`; never trust raw `**kwargs`.
- Audit all create/update/delete on tenant data via
  `app/services/audit.py:log_audit`. Strip `password_hash` from
  snapshots.
- Never leak sensitive fields in responses (passwords, OTPs, JWT
  internals).

### Testing
- Add/update tests when changing behaviour. Keep the suite green —
  151 tests today, all run on every push that touches `backend/**`.
- Don't leave broken imports or a failing startup.

---

## Admin panel (`admin-panel/`)

- **Path alias**: `@/*` for `src/*`. No deep relative imports.
- **HTTP**: a single Axios instance in `@/api/client`. Don't import
  Axios directly in feature code.
- **Server state**: TanStack Query for ALL backend data. Don't store
  it in React state or Context. The exception is auth state (lives
  in `AuthContext` because the router redirect needs it synchronously).
- **Auth token**: lives in `localStorage` (XSS risk accepted until
  refresh tokens ship). When refresh tokens land, move the refresh
  token to an HttpOnly cookie and keep the access token in memory.
- **Feature modules**: `src/features/<name>/` with `api.ts`,
  `components/`, `pages/`, `types.ts`, `index.ts`. See
  `docs/FRONTEND_NEXT_STEPS.md` for the checklist.
- Mirror backend Pydantic shapes in `types.ts`. Look at
  `backend/app/schemas/<thing>.py` for the canonical shape.

---

## Mobile app (`mobile-app/`)

- **Riverpod** for state. Shared primitives (`apiClientProvider`,
  `authProvider`) in `lib/core/`. Feature providers per feature.
- **Single Dio client** in `lib/core/api/api_client.dart`. Auth
  interceptor attaches `Bearer` token; 401 clears storage.
- **Token storage**: `flutter_secure_storage` (Keychain /
  EncryptedSharedPreferences). Not SharedPreferences.
- **Env**: compile-time via `--dart-define-from-file=.env`. No
  runtime `.env` is bundled.
- **Routing**: `go_router` with auth-aware redirects, not imperative
  `Navigator.push`.
- **Employee login** uses roll number (`/auth/employee/login`), not
  email. Admin endpoint is different.
- Hand-written `fromJson` factories for now. Move to Freezed +
  json_serializable when model count exceeds ~10.

---

## Working style

- Output is concise. Match response length to task complexity.
- Reference files as `path:line` for navigation.
- Use `TaskCreate` / `TaskUpdate` for any multi-step task.
- When asked an exploratory question, give a recommendation + the
  tradeoff in 2–3 sentences. Don't implement until the user agrees.
- Before risky / hard-to-reverse actions (destructive git, force
  push, schema drop), confirm with the user.
- Don't commit unless the user explicitly asks.

---

## Reference docs

| Doc | When |
|---|---|
| `docs/MONOREPO_GUIDE.md` | Anything about workspace structure, compose, CI, env, dev workflow |
| `docs/PROJECT_STATUS.md` | Phase status, what's shipped, what's next |
| `docs/CURRENT_ARCHITECTURE.md` | Stack details, auth flow, tenant model, technical decisions |
| `docs/FRONTEND_NEXT_STEPS.md` | Picking up admin-panel work |
| `docs/MOBILE_NEXT_STEPS.md` | Picking up mobile-app work |
| `backend/API_AUDIT.md` | Endpoint-by-endpoint backend remediation status |
| `backend/Readme.md` | Backend setup, run, test, deploy |
