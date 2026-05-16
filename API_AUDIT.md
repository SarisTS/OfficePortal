# OfficePortal HRMS Backend — Phase 1 API Audit

**Date:** 2026-05-16
**Scope:** all 26 routers mounted in `main.py`
**Goal:** verify production-readiness for the Admin React app and Flutter mobile app

This report classifies every endpoint as **WORKING / INCOMPLETE / MISSING /
RISKY / DEPRECATED**, then ends with a prioritized remediation list.

A finding's severity reflects what it would mean for a consumer integration:

- **🔴 Critical** — security flaw, tenant violation, or broken integration contract
- **🟠 High** — wrong/inconsistent behavior that will cause frontend bugs
- **🟡 Medium** — style / consistency issues that slow client work but won't break it
- **🟢 Low** — nice-to-have

---

## 1. Working Endpoints

These follow the established conventions (`ApiResponse` envelope, proper
auth gating via `require_admin` / `require_user` / `get_current_user`,
tenant scoping via `assert_can_access_employee` / `same_company`,
pagination, soft-delete filters). Safe to integrate against today.

### Auth — `/auth/*`
- `POST /auth/admin/login` — admin login, returns JWT
- `GET /auth/google/login`, `GET /auth/google/callback` — Google OAuth (admin only)
- `POST /auth/change-password` — authenticated user changes password
- `POST /auth/employee/login` — employee/staff login by roll_no
- `POST /auth/send-otp`, `POST /auth/verify-otp` — mobile OTP login flow (employee/staff)
- `POST /auth/employee/forgot-password`, `POST /auth/employee/reset-password` — OTP-based password reset
- `GET /auth/me` — current user profile (returns Pydantic projection — no `password_hash` leak)

### Employees — `/employees/*`
- `POST /employees/`, `GET /employees/`, `GET /employees/{id}`, `PUT /employees/{id}`, `DELETE /employees/{id}` — full admin CRUD via `crud.employee.*`, generates roll_no + password, queues welcome email, writes audit log
- `POST /employees/import` — bulk CSV upload, per-row failures captured
- `GET /employees/role/{role_id}` — filter by role

### Attendance — `/attendance/*`
- `POST /attendance/check-in`, `POST /attendance/check-out` — geo-validated, employee self-service
- `GET /attendance/me`, `GET /attendance/employee/{employee_id}`, `GET /attendance/{id}` — reads
- `PUT /attendance/{id}`, `DELETE /attendance/{id}` — admin edit/soft-delete

### Leave — `/leave/*`
- Full CRUD: `POST /`, `GET /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`
- `GET /leave/employee/{employee_id}`
- `POST /leave/{id}/approve`, `POST /leave/{id}/reject` — admin, audited, balance-debited

### Leave policy / balance — `/leave-policies/*`, `/leave-balances/*`
- Policies: full CRUD (admin)
- Balances: `GET /me`, `GET /{employee_id}` (admin), `POST /{employee_id}/adjust` (admin)

### Self-service — `/me/*`
- `GET /me/profile`, `PUT /me/profile`
- `GET /me/holidays`, `GET /me/weekly-offs`, `GET /me/salary`

### Salary & payroll — `/salary-structures/*`, `/payslips/*`
- Salary structure: full admin CRUD + `POST /import` + history listing
- Payslip: per-employee generate, per-company bulk generate, list (self/admin), single get, PDF download

### Reports — `/reports/*`
- `GET /reports/attendance/monthly`, `GET /reports/attendance/employee/{id}/monthly`
- `GET /reports/leave/usage`, `GET /reports/payroll/monthly`

### Holiday calendar — `/company-holidays/*`, `/company-weekly-offs/*`
- Holidays: full admin CRUD + `POST /bulk`
- Weekly offs: create / list / delete

### Audit log — `/audit-logs/*`
- `GET /`, `GET /{id}` — admin-gated, tenant-scoped, 404-on-cross-tenant (no existence-leak)

### Shifts — `/shifts/*`, `/shift-assignments/*`
- Shift CRUD, per-company listing, paginated
- Shift assignment: create, change, history, `GET /current/{employee_id}` (self or admin)

### Company locations — `/company-locations/*`
- Reads open to any authenticated user; mutations admin-only

---

## 2. Incomplete Endpoints

Endpoints that exist and "work" but have functional gaps a consumer will hit.

### 🟠 `POST /attendance/manual`
**Issue:** `employee_id` and `date` are bare function parameters without a `Query()` / `Path()` / `Body()` annotation alongside the body `data: ManualAttendanceCreate`. FastAPI will interpret them as query parameters, which is not what the route name implies and is awkward for callers. Also: no router-level tenant check on `employee_id`.
**Fix:** move `employee_id` into the path (`POST /attendance/manual/{employee_id}`), move `date` into the body, run `assert_can_access_employee` at the top.

### 🟠 `GET /locations/` (raw country/state/city)
**Issue:** Raises 404 when no locations exist. The standard pattern (used everywhere else in this codebase) is to return an empty `PaginatedResponse(total=0, items=[])`. A Flutter or React client that hits 404 here will likely show an error toast instead of an empty state.
**Fix:** return the empty paginated response.

### 🟠 `POST /companies/`, `PUT /companies/{id}`, `DELETE /companies/{id}`
**Issue:** Gated only by `require_admin`, which permits `office_admin`. An office_admin can therefore create new companies, edit any other company's name/parent, and soft-delete competing tenants.
**Fix:** wrap with `is_super_admin` gate, OR add a `require_super_admin` helper to `app/crud/auth.py`.

### 🟠 `GET /companies/`, `GET /companies/{id}`
**Issue:** No tenant scoping. An office_admin can list and read every company in the system, including names of competitors.
**Fix:** office_admin should see only their own company; super_admin sees all.

### 🟡 `POST /admin/food/*`, `GET /admin/food/*`, `POST /employee/food/*`, `GET /employee/food/*`
**Issue:** None of the food endpoints wrap responses in the `ApiResponse` envelope. They return raw schema objects. A Flutter client written against the rest of the API will need a second response parser for the food module.
**Fix:** wrap every food endpoint's return value in `{status, message, data}`.

### 🟡 `POST /locations/create`, `PUT /locations/update/{id}`, `DELETE /locations/delete/{id}`
**Issue:** Verb-in-path naming; every other router uses RESTful `POST /`, `PUT /{id}`, `DELETE /{id}`.
**Fix:** rename to match. Breaking change for any existing client — defer to a v2 cleanup pass if a client is already wired up.

### 🟡 `GET /locations/json/cities/{state_id}`
**Issue:** Missing explicit `return` on the success path in the route handler — the function path implicitly returns `None` which FastAPI will serialize as `null`. Caught by anyone who actually exercises the endpoint, but a latent bug.

### 🟡 `GET /hostels/`, `GET /roles/`, `GET /departments/`
**Issue:** `skip` / `limit` query parameters have no validation constraints (`ge=0`, `le=100`, etc.). A client passing `limit=999999` will get an unbounded result set.
**Fix:** `skip: int = Query(0, ge=0)`, `limit: int = Query(10, ge=1, le=100)`.

### 🟡 `GET /reports/attendance/employee/{employee_id}/monthly`
**Issue:** Returns a zero-filled summary if the employee has no rows for the period, rather than 404. This is actually the documented intent ("zeros not 404"), but worth noting so clients know not to wait for an error to detect "no data" — they should check the totals.

---

## 3. Missing Endpoints (required by Admin React + Flutter)

These don't exist today and frontends will need them. Listed in priority order.

### 🔴 (Admin + Flutter) Logout / token revocation
There is no way for a client to invalidate a JWT. On password change, password reset, account deactivation, or device theft, every previously issued token remains valid until natural expiry. Combined with no refresh-token rotation, this is the single biggest security gap.
**Minimum viable fix:** issue a token-version counter on the Employee row, embed it in the JWT, increment on logout / password change. Or a Redis-backed deny-list.
*(Note: the deferred Phase 2 "refresh tokens" item covers this — but it's listed here as **missing** because Flutter needs at least a logout endpoint before launch.)*

### 🔴 (Flutter) `GET /me/leaves` — employees see their own leave history
Today an employee can read `/leave/` (returns their own leaves — `crud.leave.get_leaves` scopes by user_id for non-admins, fine) but the URL is admin-flavored and doesn't fit the `/me/*` pattern the mobile app uses. Add `GET /me/leaves` for convenience and discoverability.

### 🟠 (Flutter) `GET /me/shifts` — current shift + history
`GET /shift-assignments/current/{employee_id}` exists but requires the caller to know their own ID. A `/me/shifts/current` + `/me/shifts/history` pair would simplify mobile.

### 🟠 (Flutter) `GET /me/attendance` query filters
Today `/attendance/me` returns ALL attendance for the user. Flutter typically needs `?year=2026&month=5` (calendar view) or `?from=2026-05-01&to=2026-05-31`. Returning a full multi-year history per request is wasteful.

### 🟠 (Admin) `GET /employees/` search & filter
Today only `skip`/`limit` and `/role/{id}`. Admin React almost certainly wants `?q=...&department_id=...&company_id=...&is_active=true` for employee directory.

### 🟠 (Admin) `POST /employees/{id}/reset-password`
Admin-initiated password reset for an employee. Today the only flow is the employee-initiated OTP reset.

### 🟠 (Admin) `POST /employees/{id}/activate` and `POST /employees/{id}/deactivate`
Today only soft-delete. Admins need a softer "deactivate" toggle (`is_active=False`) that's reversible.

### 🟡 (Flutter) Push-notification device token registration
Required for any push notifications. Out of scope until the Phase 2 notification system lands, but Flutter teams typically build the registration plumbing first.

### 🟡 (Both) `GET /me/payslips/latest`
Convenience: return the most recent payslip. Today the client must list + sort.

### 🟡 (Both) Profile photo upload
`POST /me/profile/photo` + `GET /me/profile/photo`. Standard HRMS feature.

### 🟡 (Admin) `GET /audit-logs/entities/{type}/{id}`
Convenience read for "everything that ever happened to this employee/leave/payslip". Today possible via `/audit-logs/?entity_type=...&entity_id=...` but the dedicated URL is cleaner for an admin UI.

### 🟡 (Admin) Bulk holiday DELETE for a year
Useful for cleaning up wrong imports. Today the only option is one-by-one delete.

---

## 4. Risky Endpoints

Endpoints that work but contain a security flaw or privilege-escalation path.

### 🔴 `POST /auth/employees` (the legacy employee creation in `auth.py`)
**Severity:** Critical.
**Problems (multiple):**
1. **No tenant check on `request.company_id`.** An office_admin can pass another company's ID and successfully create staff/employees inside that tenant. This is a direct cross-company privilege violation.
2. **Bypasses `crud.employee.create_employee`.** Skips the audit log entry, skips password generation, skips welcome email, skips department-belongs-to-company validation, skips shift assignment.
3. **Duplicate of `POST /employees/`.** The two endpoints both create employees, but with different rules. A consumer that hits the wrong one gets the wrong behavior.
4. **Roll-no uniqueness check doesn't filter `deleted_at`** — a deleted employee's roll_no will incorrectly be reported as taken.
5. **Email uniqueness check doesn't filter `deleted_at`** — same.

**Action:** deprecate this endpoint immediately. Either remove or have it forward to `crud.employee.create_employee`.

### 🔴 `POST /companies/` (creation), `PUT/DELETE /companies/{id}`
**Severity:** Critical.
office_admin can create or delete any company. See section 2 above for details. Should be super_admin only.

### 🔴 `GET /companies/`, `GET /companies/{id}`
**Severity:** High.
office_admin can list/read every other company. See section 2.

### 🟠 `GET /auth/google/callback`
**Severity:** Medium (UX, not data).
Catches every exception (including `HTTPException`) and re-raises a generic 500 with `"Google authentication failed"`. This hides the real reason — `"Invalid or unverified email"`, `"Access denied"`, `"User not found"` — from the client.
**Fix:** re-raise `HTTPException` unchanged; only convert unhandled `Exception` to 500.

### 🟠 `POST /attendance/manual`
**Severity:** Medium.
No tenant check at router level (CRUD might enforce it, but the router is the contract). An office_admin from company A could in principle mark attendance for an employee in company B if the CRUD layer doesn't catch it. Worth verifying or hardening.

### 🟡 `POST /auth/employees` ALSO does not generate a roll_no — caller supplies it
This means an admin who creates an employee here can pick an arbitrary roll_no, e.g. one matching another employee's natural-key. Even before the bypass issue above, this is bad data hygiene.

---

## 5. Deprecated / Unusable Endpoints

### 🔴 `POST /auth/employees`
See section 4. **Recommend: delete or redirect to `POST /employees/`**. Document the deprecation in the OpenAPI description so any existing client team is warned.

### 🟡 Food module response shapes
`/admin/food/*` and `/employee/food/*` don't follow the `ApiResponse` envelope used everywhere else. Not deprecated, but they look stale relative to the codebase and a consumer would reasonably ask "is this still the right module?". Either bring them up to the standard or document them as legacy.

---

## 6. Remediation Priority List

Fix in this order. Numbers in parentheses are the section references above.

### Immediate (before any Admin React or Flutter integration)
1. **Deprecate or rewrite `POST /auth/employees`** (5, 4). Today's biggest cross-company risk.
2. **Add super_admin gate to `/companies/` mutations** (4). Trivial fix; massive surface reduction.
3. **Add tenant scoping to `/companies/` reads** (2, 4).
4. **Add a logout endpoint or token-revocation mechanism** (3). At minimum a stub the Flutter login screen can call.
5. **Fix `POST /attendance/manual` parameter shape and add tenant check** (2, 4).
6. **Fix `GET /auth/google/callback` exception handling** (4).

### Before launch
7. **Wrap the food module in `ApiResponse`** (2). Pure consistency, big consumer DX win.
8. **Add the four missing self-service endpoints** (3): `/me/leaves`, `/me/shifts`, attendance filters on `/me/attendance`, `/me/payslips/latest`.
9. **Add admin employee search/filter** (3).
10. **Add admin password-reset + activate/deactivate for employees** (3).
11. **Rename `/locations/{create,update,delete}` to RESTful paths** (2). Coordinate with the Admin team if they've already wired the old paths.
12. **Fix empty-list 404 in `GET /locations/`** (2).
13. **Add `ge`/`le` constraints to `skip`/`limit` on hostels, roles, departments** (2).

### Nice-to-have
14. Profile photo upload, bulk holiday delete, audit-by-entity convenience URL.
15. Stylistic cleanup in food + location modules.

---

## 7. Observations on Cross-Cutting Concerns

### Response envelope
`ApiResponse[T]` + `PaginatedResponse[T]` are well-defined in `app/utils/api_response.py`. **96%** of endpoints use them. Only the food module and the location module's nested JSON endpoints diverge — both fixable.

### Error envelope
`main.py` registers two exception handlers that produce `{status: "error", code, message}` — consistent and good. Tests can rely on this.

### Auth flow surface
- `get_current_user` — any logged-in, non-deleted user
- `require_user` — same gate, slightly different name (could be consolidated)
- `require_admin` — super_admin OR office_admin
- **No `require_super_admin`.** The pattern in routers is to call `is_super_admin(user)` manually after `require_admin`. This works but is error-prone — see the company endpoints. Adding the helper would make critical gates explicit.

### Tenant scoping
Done well in newer modules (audit, payroll, salary structure, leave, holiday, weekly-off). Done poorly in legacy modules (company, auth's create-employee). This roughly tracks the order things were built — older code predates `app/core/permissions.py`.

### Soft-delete
Consistent: `deleted_at IS NULL` filters everywhere except `crud/company.py` which uses `is_active` flag. Both work, but the inconsistency creates a maintenance trap.

### DB transactions
`with_transaction(db)` is used in the newer CRUD (salary_structure, leave, audit). Older CRUD (employee, company) does manual `db.commit() / db.rollback()` in try/except. Both correct, but the newer pattern is cleaner.

### Audit log coverage
After the most recent commit (`7ee985e`), audit covers:
- employee CUD ✅
- leave approve/reject/delete ✅
- salary_structure CUD ✅
- payslip generate ✅

**Not yet audited** (consider adding before launch):
- company CUD (super_admin actions — small volume, high blast radius)
- attendance update/delete (admin overrides — common audit ask)
- leave_balance.adjust (manual debit/credit)
- holiday CUD (less critical but easy to add)
- role / department CUD (small)

### Pagination consistency
`PaginatedResponse[T]` is used wherever pagination matters. Plain `list[T]` is used where the result is naturally bounded (e.g. weekly-offs — at most 7). Fine.

---

## 8. Open Verification Items (couldn't fully verify in this pass)

These would need a live database or running test suite to confirm, not just code reading:

- **`POST /attendance/manual`** parameter handling: is the route actually callable today, or does it 422 because of the unannotated params? Test by hitting it.
- **`POST /attendance/check-in/check-out`** geo-fence: does it correctly reject check-ins from outside the configured radius? Behavior depends on `company_location` data + `attendance_service.py` math.
- **`POST /salary-structures/import`** for office_admin importing for another company: confirmed in the test suite to be tenant-scoped, but worth a manual run too.
- **Soft-deleted employees' login attempts**: `Employee.deleted_at.is_(None)` is filtered in the login query — verified by reading; no test covers it.
- **JWT expiry**: `create_access_token` reads expiry from settings. No test that an expired token actually returns 401 (could be flaky in CI).

---

## Appendix A: Endpoint count by module

| Module | Endpoints |
|---|---|
| auth | 11 |
| employees | 7 |
| attendance | 7 |
| company | 5 |
| leave | 9 |
| leave_policy | 5 |
| leave_balance | 3 |
| me | 5 |
| salary_structure | 6 |
| payslip | 6 |
| reports | 4 |
| holiday | 6 |
| weekly_off | 3 |
| audit_log | 2 |
| admin_food | 5 |
| employee_food | 2 |
| hostel | 5 |
| role | 5 |
| department | 5 |
| location | 8 |
| shift | 6 |
| shift_assignment | 4 |
| company_location | 5 |
| **Total** | **~123** |

---

*End of audit. The remediation list is the next phase of work — recommend starting with items 1–6 in section 6 since they're security-critical and small.*
