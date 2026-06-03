/**
 * Role -> dashboard route mapping, shared by the proxy-adjacent client guard
 * and the auth pages that redirect already-authenticated users.
 */

import type { UserRole } from "@/lib/api/types";

export const DASHBOARD_BY_ROLE: Record<UserRole, string> = {
  passenger: "/passenger",
  driver: "/driver",
  admin: "/admin",
};

export function dashboardPath(role: UserRole): string {
  return DASHBOARD_BY_ROLE[role] ?? "/passenger";
}

/** Auth pages a logged-in user should be bounced away from. */
export const AUTH_PATHS = [
  "/login",
  "/register",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
];

/** Route prefixes that require an authenticated session. */
export const PROTECTED_PREFIXES = ["/passenger", "/driver", "/admin"];
