/**
 * JWT storage helpers.
 *
 * We store the access token in localStorage. The XSS attack surface this
 * exposes (a successful XSS can read the token) is acceptable for now
 * because:
 *   - the backend's stub /auth/logout doesn't yet support real revocation
 *     (Phase 2 backlog: refresh tokens with server-side deny-list)
 *   - the access token's lifetime is bounded by ACCESS_TOKEN_EXPIRE_MINUTES
 *     on the server
 *
 * When refresh tokens land, the refresh token should move to an
 * HttpOnly cookie and the access token can stay in memory only.
 */
const ACCESS_TOKEN_KEY = "officeportal.admin.access_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}
