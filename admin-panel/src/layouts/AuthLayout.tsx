import { Outlet } from "react-router-dom";

/**
 * Centered card shell for unauthenticated screens (login, password reset,
 * etc.). Pages render inside the white card via <Outlet />.
 */
export function AuthLayout() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-md p-8">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-semibold text-slate-900">
            OfficePortal
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            HR administration console
          </p>
        </div>
        <Outlet />
      </div>
    </div>
  );
}
