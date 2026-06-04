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

/**
 * Cursor-pagination metadata (`apps/common/pagination.py`). `next`/`prev` are full
 * absolute URLs already carrying `?cursor=<opaque>`; `null` marks the boundary.
 * There is no `count` and the key is `prev`, not `previous`. NEVER pass these URLs
 * back through `api` — extract the cursor token and re-issue the relative endpoint.
 */
export interface PaginationMeta {
  next: string | null;
  prev: string | null;
  page_size: number;
}

/** Envelope shape for the cursor-paginated list endpoints. */
export interface PaginatedEnvelope<T> {
  data: T[];
  meta: { pagination: PaginationMeta };
  /** Always null on success; typed loosely so the defensive unwrap check holds. */
  errors: ApiErrorItem[] | null;
}

/** Bus lifecycle states (`BusStatus` enum). */
export type BusStatus = "active" | "idle" | "maintenance" | "retired";

/** A transit route as returned by the list endpoints. */
export interface Route {
  id: number;
  name: string;
  /** `#`-prefixed hex string, e.g. "#3366ff". */
  color: string;
  /** Estimated traversal time in minutes. */
  estimated_duration: number;
  created_at: string;
}

/** A single stop on a route. `lat`/`lng` are decimal STRINGS, not numbers. */
export interface BusStop {
  id: number;
  name: string;
  /** Decimal string, e.g. "27.678900" — parseFloat before any map math. */
  lat: string;
  /** Decimal string, e.g. "85.316700" — parseFloat before any map math. */
  lng: string;
  /** FK id of the owning route. */
  route: number;
  sequence: number;
  created_at: string;
}

/** Route detail adds the raw polyline + ordered stops (retrieve/create/update). */
export interface RouteDetail extends Route {
  /** Raw jsonb array of `[lat, lng]` pairs; unvalidated, may be `[]`. */
  polyline_json: Array<[number, number]> | unknown[];
  /** Stops ordered by `sequence`. */
  stops: BusStop[];
}

/** A bus in the fleet. `assigned_driver` is an int FK in reads. */
export interface Bus {
  id: number;
  plate: string;
  capacity: number;
  status: BusStatus;
  /** FK id of the assigned driver, or null. */
  assigned_driver: number | null;
  /** Read-only convenience field, or null when unassigned. */
  assigned_driver_email: string | null;
  created_at: string;
}

/** A driver (`User` with `role=driver`). The `role` field is intentionally absent. */
export interface Driver {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  is_verified: boolean;
  created_at: string;
}

/** Trip lifecycle states (`TripStatus` enum). */
export type TripStatus = "scheduled" | "in_progress" | "completed" | "cancelled";

/** A scheduled/active trip as returned by the trip endpoints (`TripSerializer`). */
export interface Trip {
  id: number;
  /** FK id of the bus. */
  bus: number;
  bus_plate: string;
  /** FK id of the route. */
  route: number;
  route_name: string;
  /** FK id of the driver. */
  driver: number;
  driver_email: string;
  status: TripStatus;
  /** ISO-8601, or null before the trip starts. */
  start_time: string | null;
  /** ISO-8601, or null until the trip ends. */
  end_time: string | null;
  /** Driver-reported headcount, or null if never set. */
  passenger_count: number | null;
  created_at: string;
}

/**
 * The latest GPS breadcrumb for a trip. lat/lng/speed/heading are decimal STRINGS on
 * the wire (DRF `DecimalField`) — `parseFloat` before any map math. `heading` may be null.
 */
export interface LastPosition {
  lat: string;
  lng: string;
  speed: string;
  heading: string | null;
  /** ISO-8601 with microseconds + offset. */
  timestamp: string;
}

/** Trip + its last known position (`/trips/active/` and `/admin/fleet/`; not paginated). */
export interface ActiveTrip {
  trip: Trip;
  last_position: LastPosition | null;
}
