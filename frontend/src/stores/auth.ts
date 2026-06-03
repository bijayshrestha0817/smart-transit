/**
 * Client-side auth store.
 *
 * Holds ONLY the current user object (hydrated from GET /auth/me/) — never tokens.
 * Tokens live exclusively in HttpOnly cookies the browser manages; storing any
 * token here (or in web storage) is forbidden by the security contract.
 *
 * This store is intentionally NOT persisted: a page reload re-derives auth state
 * from the server via the `useMe` query, so there is nothing to rehydrate from
 * localStorage and no token to leak.
 */

import { create } from "zustand";

import type { User } from "@/lib/api/types";

interface AuthState {
  user: User | null;
  /** True once the initial /auth/me/ check has settled (resolved or failed). */
  isResolved: boolean;
  setUser: (user: User | null) => void;
  setResolved: (resolved: boolean) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isResolved: false,
  setUser: (user) => set({ user }),
  setResolved: (isResolved) => set({ isResolved }),
  clear: () => set({ user: null }),
}));
