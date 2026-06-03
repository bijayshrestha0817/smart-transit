/**
 * Typed wrappers for the `/api/v1/auth/` endpoints.
 *
 * Each function unwraps the `{ data, meta, errors }` envelope and returns the bare
 * payload, or throws an `ApiError` (via the Axios interceptor + `toApiError` at the
 * call site). No tokens are ever read or stored here — auth rides in HttpOnly
 * cookies set by the backend.
 */

import { api } from "@/lib/axios";

import { unwrap } from "./error";
import type { ApiEnvelope, DetailPayload, User } from "./types";

export interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

/** POST /auth/register/ -> 201, data = created user. */
export async function register(input: RegisterInput): Promise<User> {
  const { data } = await api.post<ApiEnvelope<User>>("/auth/register/", input);
  return unwrap(data);
}

/** POST /auth/verify-email/ -> 200 { detail }. Codes: token_expired, token_invalid. */
export async function verifyEmail(token: string): Promise<DetailPayload> {
  const { data } = await api.post<ApiEnvelope<DetailPayload>>("/auth/verify-email/", {
    token,
  });
  return unwrap(data);
}

/** POST /auth/login/ -> 200, data = user; sets st_access + st_refresh cookies. */
export async function login(input: LoginInput): Promise<User> {
  const { data } = await api.post<ApiEnvelope<User>>("/auth/login/", input);
  return unwrap(data);
}

/** POST /auth/logout/ -> 204; clears cookies. Requires auth. */
export async function logout(): Promise<void> {
  await api.post("/auth/logout/");
}

/** POST /auth/forgot-password/ -> 200 (always the same message). */
export async function forgotPassword(email: string): Promise<DetailPayload> {
  const { data } = await api.post<ApiEnvelope<DetailPayload>>("/auth/forgot-password/", {
    email,
  });
  return unwrap(data);
}

/** POST /auth/reset-password/ -> 200 { detail }. Codes: token_expired, token_invalid + field errors. */
export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<DetailPayload> {
  const { data } = await api.post<ApiEnvelope<DetailPayload>>("/auth/reset-password/", {
    token,
    new_password: newPassword,
  });
  return unwrap(data);
}

/** GET /auth/me/ -> 200, data = current user. 401 if unauthenticated. */
export async function getMe(): Promise<User> {
  const { data } = await api.get<ApiEnvelope<User>>("/auth/me/");
  return unwrap(data);
}
