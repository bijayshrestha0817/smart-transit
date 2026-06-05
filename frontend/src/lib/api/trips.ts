/**
 * Typed wrappers for the trip endpoints: admin CRUD (`/admin/trips/`), the driver
 * lifecycle (`/driver/trips/...`), and the live snapshots (`/trips/active/`,
 * `/admin/fleet/`).
 *
 * Same envelope contract as the other `lib/api/*` modules: list endpoints use
 * `unwrapPage` (cursor pagination); the live snapshots return a bare `data` array
 * (no pagination); everything else returns a single object via `unwrap`.
 */

import { api } from "@/lib/axios";

import { unwrap, unwrapPage } from "./error";
import { stripUndefined } from "./params";
import type {
  ActiveTrip,
  ApiEnvelope,
  PaginatedEnvelope,
  PaginationMeta,
  Trip,
  TripStatus,
} from "./types";

/** Filters accepted by the admin trip list. */
export interface AdminTripListParams extends Record<string, unknown> {
  status?: TripStatus;
  route?: number;
  bus?: number;
  driver?: number;
  search?: string;
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

/** Filters accepted by the driver's own trip list (scoped to the driver server-side). */
export interface DriverTripListParams extends Record<string, unknown> {
  status?: TripStatus;
  ordering?: string;
  cursor?: string;
  page_size?: number;
}

/** Admin scheduling payload. `status` defaults to `scheduled` server-side. */
export interface AdminTripInput {
  bus: number;
  route: number;
  driver: number;
  status?: TripStatus;
}

/** One GPS breadcrumb in an offline-flush batch (client-supplied timestamp). */
export interface GpsBatchPoint {
  /** Decimal string rounded to 6 dp. */
  lat: string;
  /** Decimal string rounded to 6 dp. */
  lng: string;
  /** Decimal string rounded to 2 dp. */
  speed: string;
  /** Decimal string rounded to 2 dp, or omitted. */
  heading?: string;
  /** Client ISO-8601 timestamp (offline replay). */
  timestamp: string;
}

// ── Admin CRUD ───────────────────────────────────────────────────────────────

/** GET /admin/trips/ -> 200, cursor-paginated (IsAdmin). */
export async function adminListTrips(
  params: AdminTripListParams = {},
): Promise<{ rows: Trip[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Trip>>("/admin/trips/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** GET /admin/trips/{id}/ -> 200. */
export async function getAdminTrip(id: number): Promise<Trip> {
  const { data } = await api.get<ApiEnvelope<Trip>>(`/admin/trips/${id}/`);
  return unwrap(data);
}

/** POST /admin/trips/ -> 201. Codes: invalid_bus, invalid_route, invalid_driver, required. */
export async function createTrip(body: AdminTripInput): Promise<Trip> {
  const { data } = await api.post<ApiEnvelope<Trip>>("/admin/trips/", body);
  return unwrap(data);
}

/** PATCH /admin/trips/{id}/ -> 200. */
export async function updateTrip(
  id: number,
  body: Partial<AdminTripInput>,
): Promise<Trip> {
  const { data } = await api.patch<ApiEnvelope<Trip>>(`/admin/trips/${id}/`, body);
  return unwrap(data);
}

/** DELETE /admin/trips/{id}/ -> 204 (soft delete). */
export async function deleteTrip(id: number): Promise<void> {
  await api.delete(`/admin/trips/${id}/`);
}

// ── Driver lifecycle ───────────────────────────────────────────────────────────

/** GET /driver/trips/ -> 200, cursor-paginated, scoped to the requesting driver. */
export async function listDriverTrips(
  params: DriverTripListParams = {},
): Promise<{ rows: Trip[]; pagination: PaginationMeta }> {
  const { data } = await api.get<PaginatedEnvelope<Trip>>("/driver/trips/", {
    params: stripUndefined(params),
  });
  return unwrapPage(data);
}

/** GET /driver/trips/{id}/ -> 200 (404 if not the driver's own trip). */
export async function getDriverTrip(id: number): Promise<Trip> {
  const { data } = await api.get<ApiEnvelope<Trip>>(`/driver/trips/${id}/`);
  return unwrap(data);
}

/** POST /driver/trips/{id}/start/ -> 200 in_progress. Codes: 409 trip_already_started, 403 trip_not_assigned. */
export async function startTrip(id: number): Promise<Trip> {
  const { data } = await api.post<ApiEnvelope<Trip>>(`/driver/trips/${id}/start/`);
  return unwrap(data);
}

/** POST /driver/trips/{id}/end/ -> 200 completed. Codes: 409 trip_not_in_progress, 403 trip_not_assigned. */
export async function endTrip(id: number): Promise<Trip> {
  const { data } = await api.post<ApiEnvelope<Trip>>(`/driver/trips/${id}/end/`);
  return unwrap(data);
}

/** POST /driver/trips/{id}/passenger-count/ -> 200. Body `{ count }`. */
export async function setPassengerCount(id: number, count: number): Promise<Trip> {
  const { data } = await api.post<ApiEnvelope<Trip>>(
    `/driver/trips/${id}/passenger-count/`,
    { count },
  );
  return unwrap(data);
}

/** POST /driver/trips/{id}/gps/batch/ -> 202 `{ count }`. Up to 1000 points. */
export async function gpsBatch(
  id: number,
  points: GpsBatchPoint[],
): Promise<{ count: number }> {
  const { data } = await api.post<ApiEnvelope<{ count: number }>>(
    `/driver/trips/${id}/gps/batch/`,
    { points },
  );
  return unwrap(data);
}

// ── Live snapshots (seed before the WS stream takes over) ──────────────────────

/** GET /trips/active/?route={id} -> 200, `ActiveTrip[]` (no pagination; IsPassenger). */
export async function activeTrips(routeId: number): Promise<ActiveTrip[]> {
  const { data } = await api.get<ApiEnvelope<ActiveTrip[]>>("/trips/active/", {
    params: { route: routeId },
  });
  return unwrap(data) ?? [];
}

/** GET /admin/fleet/ -> 200, `ActiveTrip[]` for all in_progress trips (no pagination; IsAdmin). */
export async function fleetSnapshot(): Promise<ActiveTrip[]> {
  const { data } = await api.get<ApiEnvelope<ActiveTrip[]>>("/admin/fleet/");
  return unwrap(data) ?? [];
}
