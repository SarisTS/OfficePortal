import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center space-y-3">
        <p className="text-sm uppercase tracking-wide text-slate-500">
          403
        </p>
        <h1 className="text-2xl font-semibold text-slate-900">
          Access denied
        </h1>
        <p className="text-sm text-slate-600">
          Your account doesn't have permission for that page.
        </p>
        <Link
          to="/dashboard"
          className="inline-block text-sm text-slate-700 underline hover:text-slate-900"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
