/**
 * TanStack Query client factory.
 *
 * A per-mount instance keeps server state isolated across requests in the App
 * Router. Auth errors (401) are handled by the Axios refresh interceptor, so we
 * don't blindly retry them here.
 */

import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./api/error";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => {
          // Never retry auth/client errors; the interceptor owns 401 recovery.
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 2;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
}

export const QUERY_KEYS = {
  me: ["auth", "me"] as const,
};
