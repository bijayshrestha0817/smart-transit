/**
 * Edge route guard.
 *
 * HttpOnly cookies ARE readable by Next proxy (via `request.cookies`), so we
 * gate on the *presence* of `st_access`:
 *
 *   - Protected dashboards (/passenger, /driver, /admin) without the cookie ->
 *     redirect to /login (with a `?next=` so we can return after sign-in).
 *   - Auth pages while a session cookie exists -> redirect to /passenger
 *     (the client then routes to the role-correct dashboard once /auth/me/ loads).
 *
 * This is a coarse, presence-only gate. Authoritative RBAC — including role-precise
 * access and rejecting a stale/blacklisted cookie — is enforced server-side by the
 * Django backend on every API call; proxy only avoids flashing protected UI.
 */

import { NextResponse, type NextRequest } from "next/server";

import { AUTH_PATHS, PROTECTED_PREFIXES } from "@/lib/auth-routes";

const ACCESS_COOKIE = "st_access";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(ACCESS_COOKIE);

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  const isAuthPage = AUTH_PATHS.some((path) => pathname === path);

  if (isProtected && !hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthPage && hasSession) {
    return NextResponse.redirect(new URL("/passenger", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Run on app routes; skip Next internals and static assets.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.).*)"],
};
