/**
 * Wire types for the backend response envelope and domain models.
 *
 * Every endpoint returns `{ data, meta, errors }`. On success `errors` is null and
 * the payload lives in `data`; on failure `errors` is a non-empty array of
 * `{ code, field, detail }` and the HTTP status reflects the error. These mirror
 * `apps/common/response.py` and `apps/common/exceptions.py` exactly.
 */

export type UserRole = "passenger" | "driver" | "admin";

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  role: UserRole;
  is_verified: boolean;
  created_at: string;
}

/** A single normalized error from the backend envelope. */
export interface ApiErrorItem {
  /** Machine-readable code to branch on, e.g. "invalid_credentials". */
  code: string;
  /** Offending field name, or null for non-field / detail errors. */
  field: string | null;
  /** Human-readable message. */
  detail: string;
}

export interface ApiEnvelope<T> {
  data: T | null;
  meta: { message?: string } | Record<string, unknown> | null;
  errors: ApiErrorItem[] | null;
}

/** Plain `{ detail }` payloads returned by verify/forgot/reset/logout-style endpoints. */
export interface DetailPayload {
  detail: string;
}
