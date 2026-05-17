import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "@/auth/AuthContext";
import { AppRoutes } from "@/routes/AppRoutes";
import { env } from "@/lib/env";

/**
 * Shared QueryClient. Defaults:
 *   - staleTime 60s        : avoid refetching the same admin list four
 *                            times in one keystroke flurry
 *   - retry 1              : one retry on network blips; more is
 *                            disruptive for an admin UI
 *   - refetchOnWindowFocus : disabled because tabbing back into the
 *                            admin panel is a common pattern and we
 *                            don't want surprise refetches.
 *
 * Override per-query as needed via the `staleTime` etc. options on
 * `useQuery`.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
      {env.isDev && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
