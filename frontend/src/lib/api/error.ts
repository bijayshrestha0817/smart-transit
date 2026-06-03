/**
 * Typed `ApiError` + helpers for unwrapping the backend envelope.
 *
 * The backend never throws bare strings at the client — every failure arrives as
 * `{ data: null, meta, errors: [{ code, field, detail }] }` with a matching HTTP
 * status. We surface that as a structured `ApiError` so UI code can branch on
 * `error.code` (e.g. "invalid_credentials") instead of string-matching messages.
 */

import axios, { type AxiosError } from "axios";

import type { ApiEnvelope, ApiErrorItem } from "./types";

export class ApiError extends Error {
  /** Primary (first) error code from the envelope; "" if none. */
  readonly code: string;
  /** HTTP status, or 0 for network/transport failures. */
  readonly status: number;
  /** Full normalized error list from the backend. */
  readonly errors: ApiErrorItem[];

  constructor(message: string, code: string, status: number, errors: ApiErrorItem[]) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.errors = errors;
  }

  /** True if any error in the envelope carries the given code. */
  has(code: string): boolean {
    return this.errors.some((e) => e.code === code);
  }

  /** First error message for a specific field, if present. */
  fieldError(field: string): string | undefined {
    return this.errors.find((e) => e.field === field)?.detail;
  }
}

const isEnvelope = (value: unknown): value is ApiEnvelope<unknown> =>
  typeof value === "object" && value !== null && "errors" in value;

/**
 * Convert any thrown value from Axios into a typed `ApiError`.
 *
 * Handles three shapes: an enveloped error body, a non-enveloped Axios error
 * (e.g. unexpected 500 HTML), and a transport-level failure (no response).
 */
export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;

  if (axios.isAxiosError(err)) {
    const axiosErr = err as AxiosError<ApiEnvelope<unknown>>;
    const status = axiosErr.response?.status ?? 0;
    const body = axiosErr.response?.data;

    if (isEnvelope(body) && Array.isArray(body.errors) && body.errors.length > 0) {
      const [first] = body.errors;
      return new ApiError(first.detail, first.code, status, body.errors);
    }

    if (status === 0) {
      return new ApiError(
        "Could not reach the server. Check your connection and try again.",
        "network_error",
        0,
        [],
      );
    }

    return new ApiError(
      axiosErr.message || "Something went wrong. Please try again.",
      "unknown",
      status,
      [],
    );
  }

  return new ApiError("Something went wrong. Please try again.", "unknown", 0, []);
}

/**
 * Unwrap a successful envelope to its `data` payload.
 *
 * Throws an `ApiError` if the body is somehow an error envelope (defensive — the
 * Axios interceptor normally rejects non-2xx before we get here).
 */
export function unwrap<T>(envelope: ApiEnvelope<T>): T {
  if (envelope.errors && envelope.errors.length > 0) {
    const [first] = envelope.errors;
    throw new ApiError(first.detail, first.code, 0, envelope.errors);
  }
  return envelope.data as T;
}
