import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/api/types";

import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "./token";
import type {
  AuthenticatedUser,
  LoginRequest,
  LoginResponseData,
} from "./types";

/**
 * Auth context. The provider holds:
 *   - the currently signed-in user (null while unauthenticated)
 *   - a `status` flag so consumers can distinguish "still loading the
 *     /auth/me probe" from "definitely signed out"
 *   - login / logout actions that touch both the token store and the
 *     backend endpoints
 *
 * Route guards consume `status` + `user` to decide redirects; feature
 * components consume `user` directly via the `useAuth` hook (in
 * ./useAuth.ts — kept in a separate file so this one stays
 * component-only for Fast Refresh).
 */
type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthenticatedUser | null;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setStatus("unauthenticated");
      return;
    }
    try {
      // /auth/me returns ApiResponse with the full EmployeeResponse-shaped
      // payload. We narrow to AuthenticatedUser at the boundary.
      const { data } = await apiClient.get<ApiResponse<AuthenticatedUser>>(
        "/auth/me",
      );
      setUser(data.data);
      setStatus("authenticated");
    } catch {
      // 401 already cleared the token in the axios interceptor. Any
      // other failure here also means we can't trust the stored token.
      clearAccessToken();
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  // On boot, probe /auth/me with whatever token is in storage. Resolves
  // the `loading` state into either authenticated or unauthenticated.
  // This is a legitimate effect-driven sync with two external systems
  // (localStorage + the backend) — refreshUser's setStates land inside
  // an async callback so the rule's "synchronous cascading renders"
  // concern doesn't apply, but the linter can't see through the call.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      const { data } = await apiClient.post<ApiResponse<LoginResponseData>>(
        "/auth/admin/login",
        credentials,
      );
      setAccessToken(data.data.access_token);
      await refreshUser();
    },
    [refreshUser],
  );

  const logout = useCallback(async () => {
    try {
      // Server-side logout is a stub today (JWT is stateless) but we
      // still call it so the audit log records the event and future
      // refresh-token revocation has a server-side hook to attach to.
      await apiClient.post("/auth/logout");
    } catch {
      // Network or 401 — proceed with client-side logout regardless.
    }
    clearAccessToken();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, refreshUser }),
    [status, user, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
