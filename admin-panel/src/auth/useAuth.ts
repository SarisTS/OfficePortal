import { useContext } from "react";

import { AuthContext, type AuthContextValue } from "./AuthContext";

/**
 * Consumer hook for the auth context. Lives in its own file so
 * AuthContext.tsx (which exports the provider component) doesn't
 * mix component and non-component exports — a Fast Refresh
 * requirement enforced by react-refresh/only-export-components.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
