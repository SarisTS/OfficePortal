import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";

/**
 * Top-bar + left-rail shell for authenticated admin screens. Each
 * feature renders inside <Outlet />. Sidebar links are deliberately
 * sparse — the feature screens themselves haven't been built yet, so
 * this is the integration-friendly placeholder layout.
 *
 * Replace the inline nav array with a config-driven menu once feature
 * modules start landing under src/features/.
 */
const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/employees", label: "Employees" },
  { to: "/leaves", label: "Leaves" },
  { to: "/attendance", label: "Attendance" },
  { to: "/payslips", label: "Payslips" },
  { to: "/audit-logs", label: "Audit log" },
];

export function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <aside className="w-60 bg-slate-900 text-slate-200 flex flex-col">
        <div className="px-6 py-5 border-b border-slate-800">
          <p className="text-lg font-semibold">OfficePortal</p>
          <p className="text-xs text-slate-400">Admin console</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                "block px-3 py-2 rounded-md text-sm " +
                (isActive
                  ? "bg-slate-800 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-6 py-4 border-t border-slate-800 text-xs text-slate-400">
          {user?.name && (
            <div className="mb-2">
              <p className="text-slate-200 text-sm">{user.name}</p>
              <p className="capitalize">{user.user_type.replace("_", " ")}</p>
            </div>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="text-slate-300 hover:text-white text-sm underline"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
