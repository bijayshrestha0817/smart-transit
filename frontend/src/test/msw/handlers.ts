/**
 * Shared MSW helpers + base handlers.
 *
 * Most tests register their own endpoint behavior with `server.use(...)`, so the base
 * set is intentionally empty. The exported helpers build the backend `{data, meta,
 * errors}` envelope so handlers and assertions stay consistent with the real API.
 */
import { http, HttpResponse, type RequestHandler } from "msw";

/** Must match `env.apiUrl`'s dev default so axios requests resolve to mocked URLs. */
export const API = "http://localhost:8000/api/v1";

/** A successful enveloped body. */
export function ok<T>(data: T, meta: Record<string, unknown> | null = null) {
  return HttpResponse.json({ data, meta, errors: null });
}

/** A cursor-paginated enveloped body. */
export function okPage<T>(
  rows: T[],
  pagination: { next: string | null; prev: string | null; page_size: number },
) {
  return HttpResponse.json({ data: rows, meta: { pagination }, errors: null });
}

/** An error envelope with the given HTTP status + first error code. */
export function fail(
  status: number,
  code: string,
  field: string | null = null,
  detail = "error",
) {
  return HttpResponse.json(
    { data: null, meta: null, errors: [{ code, field, detail }] },
    { status },
  );
}

export { http };

export const handlers: RequestHandler[] = [];
