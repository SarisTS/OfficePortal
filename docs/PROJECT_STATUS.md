# OfficePortal — Project Status

**Last updated:** 2026-05-17

This is the single landing page for any new contributor or future
Claude session. Read this first. The companion docs in this folder
go deeper on specific areas:

| Document | Use when |
|---|---|
| [MONOREPO_GUIDE.md](./MONOREPO_GUIDE.md) | You need workspace purpose, startup commands, docker usage, dev workflow, CI strategy, env strategy |
| [CURRENT_ARCHITECTURE.md](./CURRENT_ARCHITECTURE.md) | You need stack details, auth flow, tenant model, migration head, CI structure |
| [FRONTEND_NEXT_STEPS.md](./FRONTEND_NEXT_STEPS.md) | You're picking up the React admin panel |
| [MOBILE_NEXT_STEPS.md](./MOBILE_NEXT_STEPS.md) | You're picking up the Flutter mobile app |
| `../backend/API_AUDIT.md` | You need the endpoint-by-endpoint backend audit + remediation status |

---

## Phase status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Backend stabilization (FastAPI audit + remediation) | ✅ Complete (2026-05-17) |
| Phase 2a | Monorepo restructure + scaffolds + per-workspace CI | ✅ Complete (2026-05-17) |
| Phase 2b | Admin panel feature screens | 🟡 In progress — Employees (read-only) shipped; see [FRONTEND_NEXT_STEPS.md](./FRONTEND_NEXT_STEPS.md) |
| Phase 2c | Mobile app feature screens | ⏳ Not started — see [MOBILE_NEXT_STEPS.md](./MOBILE_NEXT_STEPS.md) |
| Phase 3 | Deferred backend features (refresh tokens, notifications, TDS slabs, MFA, etc.) | ⏸ Frozen until Phase 2 ships |

---

## Phase 1 summary — backend stabilization (✅)

Drove from a single-folder FastAPI project to a production-readiness
audit + remediation. See `backend/API_AUDIT.md` for the endpoint-by-
endpoint status table.

**Commits (in order):**

| SHA | What landed |
|---|---|
| `2e83c03` | 6 critical security fixes (auth/employees cross-tenant, companies super_admin gate + tenant scoping, logout stub, manual attendance shape, google callback exceptions) |
| `63d06da` | Pagination bounds, locations RESTful aliases, food envelope, locations empty-list 404 |
| `a8e1a68` | Admin lifecycle (search/filter, password reset, activate/deactivate) + 4 self-service mobile endpoints |
| `0086ee3` | Test fixture for the new password-reset background-task email |
| `dee5ae1` | Audit coverage extension (company/attendance/holiday/leave_balance) + bulk holiday DELETE + audit-by-entity URL + JWT/soft-delete verification tests |
| `5a1b316` | Role/department audit coverage + geo-fence verification tests |

**Tests grew from 89 → 151** across `test_phase1_critical_fixes`,
`test_phase1_before_launch`, `test_phase1_nice_to_have`,
`test_phase1_geofence_and_audit`. Every Phase 1 commit was CI-green on
Linux.

**Two items explicitly deferred from Phase 1 (recorded in API_AUDIT.md
status table):**

- **Profile photo upload** — new feature, needs storage-backend
  decision (S3 vs local disk vs DB blob).
- **Soft-delete consistency on companies** — `app/crud/company.py`
  uses `is_active=False` while every other model uses `deleted_at`.
  Migration + cross-codebase query update; treat as a focused commit
  rather than a drive-by.

---

## Phase 2a summary — monorepo + scaffolds + CI (✅)

| SHA | What landed |
|---|---|
| `31e4321` | git root moved up from `backend/.git` → `OfficePortal/.git`; every backend file shows as a 100%-rename into `backend/` (no force-push, full history traceable via `git log --follow`) |
| `fe613af` | CI workflow moved to `.github/workflows/ci.yml` at repo root with `working-directory: backend` defaults and `paths: backend/**` filter |
| `06df16a` | Root `README.md`, `.gitignore`, `docs/` |
| `24156cb` | admin-panel scaffold (Vite + React 19 + TS + Tailwind v4 + Router 7 + Axios + TanStack Query 5). `npm run build` passes, ~99 KB gzipped JS. Auth foundation + role-gated layout + placeholder pages — no feature screens yet (deliberate, per scaffold-first rule). |
| `a33d637` | mobile-app Flutter Dart-side scaffold (Dio + Riverpod + go_router + flutter_secure_storage). Platform dirs (`ios/`, `android/`, etc.) are NOT generated — user must run `flutter create .` over the skeleton (documented in `mobile-app/README.md`). |
| `627b1da` | monorepo cleanup: `docker-compose.yml` and `CLAUDE.md` hoisted to repo root; per-workspace `.gitignore`s normalized to own only their language's noise (root keeps cross-cutting rules); CI compose-smoke job repointed to repo root; `docs/MONOREPO_GUIDE.md` added as the canonical workspace/docker/CI/env reference. CI green (both pytest + compose-smoke). |
| `2297011` | `.github/workflows/admin-panel.yml` — single job: `npm ci → lint → build → upload dist/`. Path-filtered to `admin-panel/**`. Plus four scaffold lint fixes that the new workflow would have blocked on: `useAuth` split out of `AuthContext.tsx` (Fast Refresh requirement), bootstrap-effect disable repositioned, `SearchInput` setState-in-effect rewritten as the React 19 conditional-setState-during-render pattern, unused `REQUIRED_KEYS` const dropped from `lib/env.ts`. CI green on first run. |
| `d0a588b` | `.github/workflows/mobile-app.yml` — single job: `flutter create . → pub get → analyze → build apk --debug → upload apk`. Path-filtered to `mobile-app/**`. Java 17 + Flutter 3.27.0 pinned via subosito/flutter-action@v2. First run failed at `flutter analyze`. |
| `a9d0c9b` | Mobile scaffold cleanup that the new workflow caught: three relative imports rewritten as `package:` form (api_client, auth_state x2), unused `package:flutter/foundation.dart` import dropped from `router.dart` (ChangeNotifier comes from material.dart). `pubspec.lock` gitignored at scaffold stage to avoid local-Flutter / CI-Flutter drift. CI green end-to-end (analyze 10s, debug APK build 179s on cold infra). |

---

## Phase 2b summary — admin panel feature screens (🟡 in progress)

| SHA | What landed |
|---|---|
| `0a05da0` | First feature module: **Employees (read-only)**. List page (filters: q + user_type + is_active; 25/page paginated) + detail page (Identity / Organisation / Address / Metadata sections). Plus 7 shared UI primitives in `src/components/` (Badge, DataTable, PageHeader, Pagination, SearchInput, Select, StateViews) — the design-system base every future feature will consume. Routes `/employees` and `/employees/:id` wired. Mutations (create/edit/delete/activate/deactivate/reset-password/CSV import) deferred to follow-up commits with react-hook-form + zod + sonner + a Modal primitive. Build: 104.6 KB gzipped (+5 KB vs scaffold). |

---

## Branch state

| Ref | SHA |
|---|---|
| `main` | `a9d0c9b` (or whatever the latest is when you read this — `git rev-parse main` to confirm) |
| `chore/env-example` | tracks `main` |
| `origin/main` | mirrors `main` |
| `origin/chore/env-example` | mirrors local |

**Working-branch convention:** all work happens on `chore/env-example`,
then fast-forward-merged to `main`, then both pushed. Per saved feedback
(see `~/.claude/projects/.../memory/feedback_branch_strategy.md`), the
user does NOT want per-feature branches.

---

## CI status

Three per-workspace workflows, each path-filtered so unrelated changes
don't burn runner minutes. All three currently green on `main`.

| Workflow | Path filter | Jobs | Last result |
|---|---|---|---|
| `ci.yml` (backend) | `backend/**`, `docker-compose.yml`, workflow file | **pytest** (151 tests, SQLite in-memory + mocked Redis, in `backend/`) + **docker compose smoke** (full Postgres + Redis + migrate + app, probes `/health`, at repo root) | ✅ on `2297011` (last triggered) |
| `admin-panel.yml` | `admin-panel/**`, workflow file | **lint + build**: `npm ci → npm run lint → npm run build → upload admin-panel-dist artefact (7-day)`. In `admin-panel/`. Node 20. | ✅ on `2297011` (last triggered) |
| `mobile-app.yml` | `mobile-app/**`, workflow file | **analyze + build apk**: `flutter create . → pub get → analyze → build apk --debug → upload officeportal-mobile-debug-apk (7-day)`. In `mobile-app/`. Java 17, Flutter 3.27.0 stable. iOS build deferred (needs macOS runner). | ✅ on `a9d0c9b` |

Concurrency groups (`ci-${ref}`, `admin-panel-${ref}`,
`mobile-app-${ref}`) cancel-in-progress so newer commits on the same
ref kill in-flight runs. See `docs/MONOREPO_GUIDE.md` §6 for the
canonical per-workspace breakdown + how to extend (e.g. iOS,
`flutter test`).

---

## Known issues

- **Mobile app is not yet runnable** — needs one-time `flutter create .`
  to add platform dirs. See [MOBILE_NEXT_STEPS.md](./MOBILE_NEXT_STEPS.md).
- **Soft-delete inconsistency** on `companies` (`is_active` instead of
  `deleted_at`). Functional, but a maintenance trap. Tracked in
  `backend/API_AUDIT.md`.
- **Logout endpoint is a stub** — JWTs remain valid until natural
  expiry. Real revocation lives in the Phase 3 refresh-token work.
- **Secrets in `backend/.env`** — Google OAuth client secret, Gmail app
  password, `SECRET_KEY` placeholder were leaked at one point. Rotation
  is the user's responsibility, out-of-band. Don't touch `.env` from
  this tooling.

---

## Recommended next steps (in priority order)

### Immediate (Phase 2b/2c)
1. **Employees mutations** — activate/deactivate + admin password
   reset first (simplest, no form library needed beyond a confirm
   modal); then create/edit (needs `react-hook-form` + `zod`); CSV
   import last. Pull in `sonner` for toast feedback when the first
   mutation lands.
2. **Next admin panel feature module** — recommended order from
   here: Audit Log (read-only, second-easiest) → Leaves
   (mutations) → Attendance → Payslips → Holidays. See
   [FRONTEND_NEXT_STEPS.md](./FRONTEND_NEXT_STEPS.md) for the
   per-feature checklist.
3. **Run `flutter create .` in `mobile-app/`** to make the Flutter
   project buildable locally. CI already does this each run, but a
   local generation lets the user iterate without pushing every time.
   One-time, no rework after.
4. **Pick the first mobile feature** — recommended order is
   Attendance (check-in/out flow) → Leaves → Payslips → Profile. See
   [MOBILE_NEXT_STEPS.md](./MOBILE_NEXT_STEPS.md).

### Later (Phase 3, after frontends ship)
4. Refresh tokens / real `/auth/logout` revocation
5. Notification system + push tokens (mobile needs this)
6. TDS slabs in payroll
7. Profile photo upload (Phase 1 deferral)
8. Soft-delete consistency on companies (Phase 1 deferral)
9. Leave carry-forward + dedicated `LeaveBalanceAdjustment` table
10. MFA, alternate-Saturday weekly pattern, per-company hostel
    scoping refinement, Pydantic `ConfigDict` migration

---

## How to set up the workspace from scratch

```bash
git clone https://github.com/SarisTS/OfficePortal.git
cd OfficePortal

# Backend stack (compose lives at the repo root)
cp backend/.env.example backend/.env
docker compose up --build         # full stack on :8000

# Admin panel (in another terminal)
cd admin-panel
cp .env.example .env.local        # adjust VITE_API_URL
npm install
npm run dev                       # :5173

# Mobile app (one-time, then flutter run)
cd ../mobile-app
flutter create . --project-name officeportal_mobile --org com.officeportal
cp .env.example .env              # adjust API_URL
flutter pub get
flutter run --dart-define-from-file=.env
```

See [`MONOREPO_GUIDE.md`](./MONOREPO_GUIDE.md) for the canonical
startup / docker / CI / env reference.
