"use client";

/**
 * Auth hooks bridging TanStack Query (server state) and the Zustand store
 * (in-memory user). `useMe` is the single source of session truth: it calls
 * GET /auth/me/ and mirrors the result into the store. No tokens are involved —
 * the request succeeds or 401s purely on the HttpOnly cookies.
 */

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { getMe, logout as logoutRequest } from "@/lib/api/auth";
import { ApiError, toApiError } from "@/lib/api/error";
import type { User } from "@/lib/api/types";
import { QUERY_KEYS } from "@/lib/queryClient";
import { useAuthStore } from "@/stores/auth";

/** Hydrate + observe the current user. Returns store-backed auth state. */
export function useMe(enabled = true) {
  const setUser = useAuthStore((s) => s.setUser);
  const setResolved = useAuthStore((s) => s.setResolved);
  const user = useAuthStore((s) => s.user);
  const isResolved = useAuthStore((s) => s.isResolved);

  const query = useQuery<User, ApiError>({
    queryKey: QUERY_KEYS.me,
    queryFn: getMe,
    enabled,
    // A 401 here means "not logged in" — a normal state, not a retryable error.
    retry: false,
  });

  useEffect(() => {
    if (query.isSuccess) {
      setUser(query.data);
      setResolved(true);
    } else if (query.isError) {
      setUser(null);
      setResolved(true);
    }
  }, [query.isSuccess, query.isError, query.data, setUser, setResolved]);

  return {
    user,
    isLoading: enabled && (query.isLoading || !isResolved),
    isAuthenticated: !!user,
    isResolved,
  };
}

/** Logout: clears server cookies, wipes client state, redirects to /login. */
export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const clear = useAuthStore((s) => s.clear);

  return useMutation({
    mutationFn: logoutRequest,
    onSettled: () => {
      // Always clear locally, even if the network call failed.
      clear();
      queryClient.removeQueries({ queryKey: QUERY_KEYS.me });
      router.replace("/login");
      router.refresh();
    },
    onError: (err) => toApiError(err),
  });
}
