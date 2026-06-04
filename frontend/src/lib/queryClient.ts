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

  // Public browse
  routes: (p?: unknown) => ["routes", p ?? {}] as const,
  route: (id: number) => ["routes", id] as const,
  stops: (p?: unknown) => ["stops", p ?? {}] as const,
  stop: (id: number) => ["stops", id] as const,

  // Admin CRUD
  adminRoutes: (p?: unknown) => ["admin", "routes", p ?? {}] as const,
  adminBuses: (p?: unknown) => ["admin", "buses", p ?? {}] as const,
  adminDrivers: (p?: unknown) => ["admin", "drivers", p ?? {}] as const,

  // Driver picker for the assign-driver dialog
  drivers: ["drivers"] as const,

  // Trips (P2 real-time)
  adminTrips: (p?: unknown) => ["admin", "trips", p ?? {}] as const,
  adminTrip: (id: number) => ["admin", "trips", id] as const,
  driverTrips: (p?: unknown) => ["driver", "trips", p ?? {}] as const,
  driverTrip: (id: number) => ["driver", "trips", id] as const,
  activeTrips: (routeId: number) => ["trips", "active", routeId] as const,
  fleet: ["admin", "fleet"] as const,
};
