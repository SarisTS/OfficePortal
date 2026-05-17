# Mobile (mobile-app) — Next Steps

**Last updated:** 2026-05-17

Picks up from the Flutter scaffold committed in `a33d637`. The scaffold
contains the **Dart side** only — auth, router, API client, login +
dashboard screens. Platform-specific directories (`ios/`, `android/`,
etc.) and a buildable Flutter project must be generated before any
feature work begins.

---

## CRITICAL — first run before anything else

```bash
cd mobile-app
flutter create . --project-name officeportal_mobile --org com.officeportal
```

`flutter create .` is non-destructive — it adds the missing `ios/`,
`android/`, `web/`, `macos/`, `linux/`, `windows/`, `test/` dirs
WITHOUT overwriting:

- `lib/` (the Dart-side scaffold)
- `pubspec.yaml`
- `analysis_options.yaml`
- `.env.example`, `.gitignore`, `README.md`

After it runs, `pubspec.yaml` may show a merge — Flutter usually
adds nothing, but check the diff before continuing. Then:

```bash
flutter pub get
cp .env.example .env
# adjust API_URL — Android emulator uses 10.0.2.2, iOS sim uses 127.0.0.1
flutter run --dart-define-from-file=.env
```

If `flutter doctor` flags missing toolchains (Xcode, Android Studio,
JDK), resolve those first — the scaffold won't help with platform-tool
gaps.

---

## What's already wired

- **Single Dio client** in `lib/core/api/api_client.dart`. Auth
  interceptor attaches `Bearer <token>` from secure storage on every
  request; 401 clears the stored token.
- **Auth state via Riverpod**. `authProvider` exposes `{status, user,
  login, logout}`. Consumers use `ref.watch(authProvider)`.
- **Token storage** in `lib/core/auth/token_storage.dart` —
  Keychain on iOS, EncryptedSharedPreferences on Android via
  `flutter_secure_storage`.
- **Compile-time env** in `lib/core/env/env.dart`. Values bake in at
  build time via `--dart-define-from-file=.env`.
- **Router** in `lib/router/router.dart` — go_router with auth-aware
  redirects (loading → `/splash`, unauthenticated → `/login`,
  authenticated → `/dashboard`).
- **Login screen** — roll number + password form posting to
  `/auth/employee/login`. Pulls error messages via
  `ApiClient.errorMessage(e)`.
- **Dashboard screen** — welcome placeholder + logout button.

---

## What's NOT wired (build these next)

### Recommended build order

Mobile users are employees, not admins. Pick screens by what an
employee does most often on their phone:

1. **Attendance — check-in / check-out** (the headline feature)
2. **Leaves — request + list own leaves**
3. **Payslips — list + view PDF**
4. **Profile — read + edit self-service fields**
5. **Holidays + weekly-offs — calendar view**

Layers that must land alongside feature work:

- **Common widgets** in `lib/widgets/`: AppButton, AppTextField,
  ErrorBanner, LoadingState, EmptyState, PullToRefresh wrapper.
- **A "data state" pattern** — `AsyncValue<T>` from Riverpod is the
  idiomatic choice. Wrap server data in `FutureProvider` /
  `StreamProvider` and pattern-match on `loading / data / error`.
- **Native permissions plumbing** — location for check-in, camera
  for profile photo (Phase 3). Use `permission_handler` package.
- **Push notifications** (Phase 3) — depends on backend notification
  system + token-registration endpoint, both not yet built.

---

## Per-feature checklist

When adding a feature under `lib/features/<name>/`:

```
lib/features/<name>/
├── <name>_screen.dart        top-level screen widget
├── <name>_providers.dart     Riverpod providers (data + actions)
├── <name>_models.dart        feature-local types (mirrors backend)
└── widgets/                  feature-local widgets
```

Steps:

1. **Add models** mirroring the backend Pydantic response shape. The
   canonical source is `backend/app/schemas/<thing>.py`. Add `fromJson`
   factories. Use `Map<String, dynamic>` access — no codegen.
2. **Add providers** for reads (`FutureProvider`) and actions
   (methods on a `StateNotifier`). Wire to `ref.watch(apiClientProvider)`
   for HTTP access.
3. **Add the screen** widget consuming the providers via
   `ref.watch(<provider>)` and pattern-matching `AsyncValue`.
4. **Register the route** in `lib/router/router.dart` and add nav
   affordance (bottom nav bar or drawer — pick when the second feature
   screen lands).

---

## Specific feature notes

### Attendance (highest priority)

- Endpoints: `POST /attendance/check-in`, `POST /attendance/check-out`,
  `GET /attendance/me?year=&month=` (or `from_date`/`to_date`).
- Geo-fence is server-validated against `CompanyLocation` rows. The
  client must request location permissions and send `lat`/`lon` in the
  POST body. Use `geolocator` package.
- "Outside allowed location" returns 400 from the backend — surface as
  a clear error toast, not a crash.
- Display the current shift via `GET /me/shifts/current` so the user
  knows what window they're checking into.

### Leaves

- Endpoints: `GET /me/leaves?year=&month=&leave_type=&status=`,
  `POST /leave/` (employee creates), `DELETE /leave/{id}` (employee
  can cancel pending; approved leaves refund the balance on delete).
- Approve/reject is admin-only — not on mobile.
- Balance check before submit: `GET /leave-balances/me?year=` returns
  the year's balances by leave_type.

### Payslips

- Endpoints: `GET /payslips/me`, `GET /payslips/me/latest`,
  `GET /payslips/{id}`, `GET /payslips/{id}/pdf` (returns
  `application/pdf`).
- Use a PDF viewer plugin (`flutter_pdfview` or `syncfusion_flutter_pdfviewer`).
- Cache the file locally — payslips are immutable once generated.

### Profile

- Endpoints: `GET /me/profile`, `PUT /me/profile` (whitelist: mobile,
  email, address fields).
- Self-service fields ONLY. `name`, `roll_no`, `role_id`, `user_type`,
  `company_id` are admin-only — backend rejects them with 422 if a
  client smuggles them in (StrictRequestModel's `extra="forbid"`).

---

## Open design decisions

- **State management granularity** — Riverpod scope per feature, or
  one big provider container? Recommended: per-feature, with shared
  primitives (`apiClientProvider`, `authProvider`) in `lib/core/`.
- **Code generation** — Freezed + json_serializable is the idiomatic
  Flutter pattern for typed models. Trade-off is the build_runner
  step. Recommended: add when the model count exceeds ~10. For now,
  hand-written `fromJson` factories (as in `auth_models.dart`).
- **Theming** — Material 3 with `ColorScheme.fromSeed(Colors.indigo)`
  today. Replace with brand theme when design lands; consider a
  `ThemeExtension` for OfficePortal-specific tokens.
- **Localization** — not wired. When needed: `flutter_localizations` +
  ARB files via `flutter gen-l10n`.
- **Offline support** — none today. If attendance check-in must work
  offline, queue the request locally and replay on reconnect; consider
  `flutter_isolate` + `sqflite`. Discuss with PM before building.

---

## Backend endpoints the mobile app will need (already exist)

| Feature | Endpoints |
|---|---|
| Auth | `POST /auth/employee/login`, `POST /auth/send-otp`, `POST /auth/verify-otp`, `POST /auth/employee/forgot-password`, `POST /auth/employee/reset-password`, `POST /auth/logout`, `GET /auth/me` |
| Profile | `GET /me/profile`, `PUT /me/profile` |
| Attendance | `POST /attendance/check-in`, `POST /attendance/check-out`, `GET /attendance/me` (with filters) |
| Leaves | `POST /leave/`, `GET /me/leaves`, `DELETE /leave/{id}` |
| Leave balance | `GET /leave-balances/me?year=` |
| Shifts | `GET /me/shifts/current`, `GET /me/shifts/history` |
| Payslips | `GET /payslips/me`, `GET /me/payslips/latest`, `GET /payslips/{id}`, `GET /payslips/{id}/pdf` |
| Holidays | `GET /me/holidays?year=&month=` |
| Weekly offs | `GET /me/weekly-offs` |
| Salary | `GET /me/salary` (current structure) |
| Food | `GET /employee/food/menu?date=`, `POST /employee/food/select` |

All responses follow `ApiResponse<T>` (`{status, message, data}`).
Errors come back with `{status: "error", code, message}` —
`ApiClient.errorMessage(e)` already handles the unwrap.

---

## Known constraints

- **No push notifications yet** — Phase 3 backend work. Mobile FCM /
  APNS registration plumbing can be built in parallel as long as it's
  feature-flagged off until the backend endpoint exists.
- **JWT is stateless** — logout is a server-side stub. Mobile clears
  local storage and the router bounces to `/login`. When refresh
  tokens ship (Phase 3), wire the refresh flow here.
- **Mobile login uses roll number, not email** — distinct endpoint
  from admin (`/auth/employee/login` vs `/auth/admin/login`).
- **Geo-fence requires CompanyLocation rows in the backend** — if the
  company has no active sites configured, check-in returns 400. The
  mobile UI should detect this and prompt the user to talk to their
  admin rather than retry.
