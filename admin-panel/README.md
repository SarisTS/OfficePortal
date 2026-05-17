# OfficePortal — admin-panel

React + Vite + TypeScript admin console for the OfficePortal HRMS.

## Stack

| Layer | Library |
|---|---|
| Build | Vite 8 |
| Language | TypeScript |
| UI | React 19 |
| Styling | Tailwind CSS v4 (via `@tailwindcss/vite`) |
| Routing | React Router 7 |
| HTTP | Axios (single instance in `src/api/client.ts`) |
| Server state | TanStack Query 5 |
| Auth | JWT in `localStorage`, axios interceptor, `<ProtectedRoute />` route guard |

## Run

```bash
cp .env.example .env.local        # set VITE_API_URL to your backend
npm install
npm run dev                       # → http://localhost:5173
```

Build + preview:

```bash
npm run build
npm run preview
```

## Folder layout

```
src/
├── api/              HTTP client (axios) + shared API response types
├── auth/             AuthProvider, useAuth hook, token storage
├── components/       cross-feature reusable UI primitives
├── features/         one folder per feature module (api / pages / etc.)
├── hooks/            generic React hooks
├── layouts/          AuthLayout (login), AdminLayout (sidebar shell)
├── lib/              env + utilities
├── pages/            top-level routed pages (login, dashboard, 404, 403)
└── routes/           route table + ProtectedRoute
```

Imports use the `@/*` alias for `src/*`. Configured in
`vite.config.ts` + `tsconfig.app.json` — keep both aligned.

## Auth flow

1. User submits `/login` form → POST `/auth/admin/login` on the backend.
2. Access token from `data.data.access_token` is written to
   `localStorage` under `officeportal.admin.access_token`.
3. AuthProvider calls `/auth/me` to populate the user object.
4. Axios interceptor attaches `Authorization: Bearer <token>` to every
   request.
5. On 401, the response interceptor clears the token; `<ProtectedRoute />`
   redirects to `/login`.
6. `/auth/logout` (server-side) is called on logout. Today this is a
   stub (JWT is stateless); when Phase 2 refresh tokens land, the
   server-side revocation will hook in there.

## Role guard

`<ProtectedRoute allowedRoles={["super_admin", "office_admin"]} />`
wraps the admin layout. A staff/employee bearer token redirects to
`/forbidden`.

## Feature status

| Module | Status |
|---|---|
| Employees | 🟡 Read-only foundation shipped (list + detail + filters + pagination, 25/page). Mutations deferred. |
| Audit log | ⏳ Not started — recommended next read-only flow |
| Leaves | ⏳ Not started (first mutation flow) |
| Attendance | ⏳ Not started |
| Payslips | ⏳ Not started |
| Holidays / weekly-offs | ⏳ Not started |

## What's NOT in this scaffold yet

- **Mutations on any feature** — create / edit / delete / activate
  flows for Employees, etc. Will land with `react-hook-form` + `zod`
  (form validation) + `sonner` (toast feedback) + a Modal primitive.
- **Tailwind theme customization** — using v4 defaults for now.
- **Form validation library** (zod / react-hook-form) — added when
  the first mutation flow lands.
- **Sorting** on tables — DataTable is sort-ready via column `id`
  but no sort controls yet.
- **URL state** for filters + pagination — currently local component
  state; revisit when the second feature module shows it'd help.

See [`../docs/FRONTEND_NEXT_STEPS.md`](../docs/FRONTEND_NEXT_STEPS.md)
for the per-feature build order and checklist.
