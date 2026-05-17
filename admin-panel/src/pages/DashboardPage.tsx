import { useAuth } from "@/auth/useAuth";

/**
 * Placeholder landing page after sign-in. Replace with real KPI cards +
 * recent activity widgets once feature modules land.
 */
export function DashboardPage() {
  const { user } = useAuth();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900">
        Welcome{user?.name ? `, ${user.name}` : ""}
      </h1>
      <p className="text-slate-600">
        Phase 2 scaffold — feature dashboards land here as each module is
        wired up.
      </p>
    </div>
  );
}
