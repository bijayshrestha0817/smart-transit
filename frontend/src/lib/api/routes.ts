/**
 * Typed wrappers for the `/api/v1/routes/` (public) and `/api/v1/admin/routes/`
 * (admin CRUD) endpoints.
 *
 * Each function unwraps the `{ data, meta, errors }` envelope and returns the bare
 * payload, or throws an `ApiError`. List endpoints use the cursor-paginated
 * envelope (`unwrapPage`); detail/write endpoints return a single object.
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ApiEnvelope,
  PaginatedEnvelope,
  PaginationMeta,
  Route,
  RouteDetail,
} from "./types";

/** Query params accepted by the public + admin route lists. */
export interface RouteListParams extends Record<string, unknown> {
  search?: string;
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

/** A single stop in the destructive assign-stops payload (no `route` key). */
export interface StopInput {
  name: string;
  lat: string;
  lng: string;
  sequence: number;
}

/** Write body for create/update route (never includes a `stops` key). */
export interface RouteInput {
  name: string;
  color: string;
  estimated_duration: number;
  polyline_json?: unknown[];
}

/** GET /routes/ -> 200, cursor-paginated list (public, AllowAny). */
export async function listRoutes(
  params: RouteListParams = {},
): Promise<{ rows: Route[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Route>>("/routes/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** GET /routes/{id}/ -> 200, route detail (polyline + ordered stops). */
export async function getRoute(id: number): Promise<RouteDetail> {
  const { data } = await api.get<ApiEnvelope<RouteDetail>>(`/routes/${id}/`);
  return unwrap(data);
}

/** GET /admin/routes/ -> 200, cursor-paginated list (IsAdmin). */
export async function adminListRoutes(
  params: RouteListParams = {},
): Promise<{ rows: Route[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Route>>("/admin/routes/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** POST /admin/routes/ -> 201, returns route detail. Codes: invalid_color, required. */
export async function createRoute(body: RouteInput): Promise<RouteDetail> {
  const { data } = await api.post<ApiEnvelope<RouteDetail>>("/admin/routes/", body);
  return unwrap(data);
}

/** PATCH /admin/routes/{id}/ -> 200, returns route detail. */
export async function updateRoute(
  id: number,
  body: Partial<RouteInput>,
): Promise<RouteDetail> {
  const { data } = await api.patch<ApiEnvelope<RouteDetail>>(
    `/admin/routes/${id}/`,
    body,
  );
  return unwrap(data);
}

/** DELETE /admin/routes/{id}/ -> 204 (soft delete). */
export async function deleteRoute(id: number): Promise<void> {
  await api.delete(`/admin/routes/${id}/`);
}

/**
 * POST /admin/routes/{id}/stops/ -> 201, returns the new stop array.
 *
 * DESTRUCTIVE FULL REPLACE: soft-deletes all current stops and inserts `stops`
 * atomically. The `route` FK is injected from the URL — the payload is exactly
 * `{ stops: [{ name, lat, lng, sequence }] }` with no `route` key.
 */
export async function assignStops(id: number, stops: StopInput[]): Promise<void> {
  await api.post(`/admin/routes/${id}/stops/`, { stops });
}
