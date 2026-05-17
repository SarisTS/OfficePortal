import axios, { AxiosError, type AxiosInstance } from "axios";

import { clearAccessToken, getAccessToken } from "@/auth/token";
import { env } from "@/lib/env";
import type { ApiErrorBody } from "./types";

/**
 * Single axios instance for the whole app.
 *
 * Interceptors:
 *   - request:  attach `Authorization: Bearer <token>` if a token is in
 *               storage. Logging/auth-required endpoints get the header;
 *               anonymous endpoints (login, password reset) work without
 *               it because the backend ignores the header on those paths.
 *   - response: on 401, clear the stored token and let the caller handle
 *               the redirect. We don't redirect here directly because
 *               this module shouldn't depend on react-router.
 */
export const apiClient: AxiosInstance = axios.create({
  baseURL: env.apiUrl,
  // 15s. Long enough for a slow mobile/staging round-trip; short enough
  // to surface a hung backend before the user gives up and reloads.
  timeout: 15_000,
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401) {
      clearAccessToken();
      // Caller / route guard decides where to send the user. We don't
      // navigate here because this module must stay router-agnostic.
    }
    return Promise.reject(error);
  },
);

/**
 * Pull the user-facing message out of an axios error.
 *
 * Backend's exception handlers wrap errors as
 * `{ status: "error", code: <int>, message: <str> }`. Falls back to the
 * axios message string and finally to a generic label.
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.message ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return "Unexpected error";
}
