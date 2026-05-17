import { Navigate, Route, Routes } from "react-router-dom";

import {
  EmployeeDetailPage,
  EmployeesListPage,
} from "@/features/employees";
import { AdminLayout } from "@/layouts/AdminLayout";
import { AuthLayout } from "@/layouts/AuthLayout";
import { DashboardPage } from "@/pages/DashboardPage";
import { ForbiddenPage } from "@/pages/ForbiddenPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

import { ProtectedRoute } from "./ProtectedRoute";

/**
 * Route table. Two layouts wrap two route groups:
 *
 *   <AuthLayout>     unauthenticated entry points (login, future
 *                    password-reset). No role guard.
 *
 *   <AdminLayout>    everything an admin uses post-login. Wrapped in
 *                    <ProtectedRoute allowedRoles=["super_admin",
 *                    "office_admin"]> so a staff/employee bearer token
 *                    cannot reach admin pages even if they sneak in
 *                    through the admin login flow.
 *
 * Feature pages slot under the admin layout. Add new <Route> entries
 * here as feature modules land — keep the leaves thin (mostly imports
 * from src/features/* index files).
 */
export function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      <Route path="/forbidden" element={<ForbiddenPage />} />

      {/* Admin routes — auth-gated AND role-gated */}
      <Route
        element={
          <ProtectedRoute allowedRoles={["super_admin", "office_admin"]} />
        }
      >
        <Route element={<AdminLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          {/*
            Placeholder routes — feature pages are stubbed here so the
            sidebar links render. Replace with real screens as feature
            modules land under src/features/.
          */}
          <Route path="/employees" element={<EmployeesListPage />} />
          <Route path="/employees/:id" element={<EmployeeDetailPage />} />
          <Route path="/leaves" element={<Placeholder name="Leaves" />} />
          <Route
            path="/attendance"
            element={<Placeholder name="Attendance" />}
          />
          <Route path="/payslips" element={<Placeholder name="Payslips" />} />
          <Route
            path="/audit-logs"
            element={<Placeholder name="Audit log" />}
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

function Placeholder({ name }: { name: string }) {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold text-slate-900">{name}</h1>
      <p className="text-slate-600">
        Feature module not yet wired. Scaffold lives in src/features/.
      </p>
    </div>
  );
}
