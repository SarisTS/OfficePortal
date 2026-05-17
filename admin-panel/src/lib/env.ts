/**
 * Typed access to import.meta.env so the rest of the codebase doesn't have
 * to repeat the `import.meta.env.VITE_*` dance + null guards.
 *
 * Variables exposed here MUST be prefixed with VITE_ in .env files —
 * Vite strips anything else for safety so server-side secrets can't leak
 * into the client bundle by accident.
 */
type RequiredKey = "VITE_API_URL";

function readRequired(key: RequiredKey): string {
  const value = import.meta.env[key];
  if (!value || typeof value !== "string") {
    throw new Error(
      `Missing required env variable ${key}. ` +
        `Copy .env.example to .env.local and fill it in.`,
    );
  }
  return value;
}

export const env = {
  apiUrl: readRequired("VITE_API_URL"),
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
} as const;
