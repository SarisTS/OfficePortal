# Frontend (admin-panel) — Next Steps

**Last updated:** 2026-05-17

Picks up from the scaffold committed in `24156cb`. The scaffold builds
clean (`npm run build` → ~99 KB gzipped JS) and the auth flow is wired
end-to-end. What remains is feature screens.

---

## Setup

```bash
cd admin-panel
cp .env.example .env.local        # set VITE_API_URL to the running backend
npm install
npm run dev                       # http://localhost:5173
```

Useful scripts:

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | `tsc -b && vite build` — type-check + production bundle |
| `npm run preview` | Serve the built bundle locally |
| `npm run lint` | ESLint over the project |

---

## What's already wired

- **Auth**: `AuthProvider` probes `/auth/me` on boot, holds user +
  status. `useAuth()` exposes `{status, user, login, logout, refreshUser}`.
- **HTTP**: single axios instance in `@/api/client` with Bearer +
  401-handling interceptors. Use `getErrorMessage(err)` to pull the
  user-facing message out of any error.
- **Router**: `<AppRoutes />` defines public routes (login, forbidden)
  + role-gated admin routes wrapped in
  `<ProtectedRoute allowedRoles={["super_admin", "office_admin"]} />`.
- **Layouts**: `<AuthLayout>` (centered card) + `<AdminLayout>`
  (sidebar with nav placeholders).
- **Pages**: LoginPage, DashboardPage, ForbiddenPage, NotFoundPage.
- **State**: TanStack QueryClient configured with `staleTime: 60s`,
  `retry: 1`, `refetchOnWindowFocus: false`. Devtools mounted in dev.
- **Tailwind v4**: live, no PostCSS config needed. Use utility classes
  in components.

---

## What's NOT wired (build these next)

The sidebar in `AdminLayout` shows placeholder routes for Employees,
Leaves, Attendance, Payslips, and Audit log. Each currently renders a
"feature module not yet wired" placeholder.

### Recommended build order

Start with the lowest-risk read-only flows so you exercise the auth +
API layers before any mutations.

1. **Employees** (list + read + filters) — most-touched admin surface
2. **Audit log** (read-only) — verifies pagination + filter UX
3. **Leaves** (list + approve/reject) — first mutation flow
4. **Attendance** (list + manual mark) — geo-fence already tested on
   backend
5. **Payslips** (list + PDF download) — exercises the file-response path
6. **Holidays + weekly-offs** (CRUD) — calendar UI

Layers below that haven't been built but will be needed for ANY feature:

- **Design system primitives** — Button, Input, Select, Table,
  Pagination, Toast, Modal. Lives in `src/components/`. Pick a base
  set before building two features; otherwise components proliferate.
- **Form library** — recommended: `react-hook-form` + `zod` for
  validation. Not installed; `npm install react-hook-form zod
  @hookform/resolvers` when the first form lands.
- **Toast / notification UI** — recommended: `sonner` (small, no peer
  deps). Add when the first mutation needs success/error feedback.
- **Layout polish** — top bar with breadcrumbs + user menu, a real
  active-state on sidebar nav, mobile-responsive drawer (low priority).

---

## Per-feature checklist

Use this template when adding a new feature module under
`src/features/<name>/`:

```
src/features/<name>/
├── api.ts          fetcher functions + useQuery / useMutation hooks
├── components/     feature-local UI (table rows, filter bars, etc.)
├── pages/          ListPage, DetailPage, CreatePage etc.
├── types.ts        feature-local TypeScript types
└── index.ts        public exports consumed by routes/
```

Steps:

1. **Add types** matching the backend Pydantic response schema. Look
   at `backend/app/schemas/<thing>.py` for the canonical shape; mirror
   in `types.ts`.
2. **Add fetchers + hooks** in `api.ts`. Use `useQuery` for reads,
   `useMutation` for writes. Wrap mutations with
   `queryClient.invalidateQueries({queryKey: ["<thing>"]})` on
   success.
3. **Add pages** that consume the hooks. Keep page components thin —
   delegate to feature-local components.
4. **Register the route** in `@/routes/AppRoutes.tsx` (replace the
   `<Placeholder />` stub for that path).
5. **Verify tenant scoping at the UI level** — the backend already
   enforces it, but the admin UI shouldn't surface affordances the
   actor can't actually use (e.g. don't show a "delete company"
   button to office_admins).

---

## Open design decisions

- **Tailwind theme customization**: using v4 defaults today. When the
  brand colors land, define them in CSS via the `@theme` directive in
  `src/index.css`. v4 doesn't use `tailwind.config.js`.
- **Table component**: build vs. TanStack Table vs. headless library.
  Recommended: TanStack Table when the first data grid lands — same
  vendor as React Query so consistent learning curve.
- **State management beyond Query**: no Redux/Zustand yet. Most admin
  state is server state (Query handles it) or URL state (Router
  handles it). Resist adding a global store unless three features
  share a need that neither covers.
- **Auth token storage** is localStorage today; XSS risk is documented
  in `src/auth/token.ts`. Don't change this until the backend ships
  refresh tokens (Phase 3) — at that point, move the refresh token to
  an HttpOnly cookie and keep the access token in memory only.

---

## Backend endpoints the admin panel will need (already exist)

This is a reference for query/mutation hooks. See `backend/API_AUDIT.md`
section 1 for the full list.

| Feature | Endpoints |
|---|---|
| Employees | `GET/POST /employees/`, `GET/PUT/DELETE /employees/{id}`, `GET /employees/?q=&department_id=&user_type=&is_active=`, `POST /employees/{id}/reset-password`, `POST /employees/{id}/(activate\|deactivate)`, `POST /employees/import` |
| Leaves | `GET/POST /leave/`, `POST /leave/{id}/(approve\|reject)`, `DELETE /leave/{id}` |
| Leave policies | `GET/POST /leave-policies/`, `GET/PUT/DELETE /leave-policies/{id}` |
| Leave balances | `GET /leave-balances/{employee_id}`, `POST /leave-balances/{employee_id}/adjust` |
| Attendance | `GET /attendance/{id}`, `GET /attendance/employee/{id}`, `PUT/DELETE /attendance/{id}`, `POST /attendance/manual/{employee_id}` |
| Payslips | `POST /payslips/employee/{id}/generate`, `POST /payslips/company/{id}/generate`, `GET /payslips/employee/{id}`, `GET /payslips/{id}/pdf` |
| Salary structures | `GET/POST /salary-structures/`, `GET /salary-structures/employee/{id}`, `PUT/DELETE /salary-structures/{id}`, `POST /salary-structures/import` |
| Companies | `GET /companies/`, `GET /companies/{id}` (super_admin can `POST/PUT/DELETE` too) |
| Holidays | `GET/POST /company-holidays/`, `GET/PUT/DELETE /company-holidays/{id}`, `POST /company-holidays/bulk`, `DELETE /company-holidays/bulk` |
| Weekly offs | `GET/POST /company-weekly-offs/`, `DELETE /company-weekly-offs/{id}` |
| Audit log | `GET /audit-logs/`, `GET /audit-logs/{id}`, `GET /audit-logs/entities/{type}/{id}` |
| Reports | `GET /reports/attendance/monthly`, `GET /reports/leave/usage`, `GET /reports/payroll/monthly` |
| Misc | `GET /shifts/`, `GET /shift-assignments/{employee_id}`, `GET /departments/`, `GET /roles/`, `GET /hostels/`, `GET /locations/` |

All responses follow the `ApiResponse[T]` envelope (`{status, message,
data}`). Mutations 4xx with `{status: "error", code, message}`.
