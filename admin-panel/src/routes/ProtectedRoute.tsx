import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/auth/useAuth";
import type { UserType } from "@/auth/types";

interface ProtectedRouteProps {
  /**
   * Optional allowlist of user_types. If omitted, any authenticated user
   * is allowed. If set, callers whose user_type is NOT in the list get
   * redirected to /forbidden.
   *
   * Default for admin-panel routes is ["super_admin", "office_admin"] —
   * apply at the layout level instead of repeating per page.
   */
  allowedRoles?: UserType[];
}

export function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    // Don't flicker to /login while the /auth/me probe is still in flight.
    // Replace with a real loading skeleton once the design system lands.
    return <div className="p-8 text-sm text-gray-500">Loading…</div>;
  }

  if (status === "unauthenticated" || !user) {
    return (
      <Navigate to="/login" state={{ from: location.pathname }} replace />
    );
  }

  if (allowedRoles && !allowedRoles.includes(user.user_type)) {
    return <Navigate to="/forbidden" replace />;
  }

  return <Outlet />;
}
