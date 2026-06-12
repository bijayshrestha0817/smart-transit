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
  /** Decimal string, e.g. "35.00". */
  fare: string;
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
  /** Route display color (hex), e.g. `#1E88E5` — used to tint the live map marker. */
  route_color: string;
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

// ── Ticketing / payments (P4) ─────────────────────────────────────────────────

/** Ticket lifecycle (`TicketStatus`). */
export type TicketStatus =
  | "issued"
  | "active"
  | "used"
  | "expired"
  | "refunded"
  | "cancelled";

/** Payment gateways (`PaymentGateway`). Only `wallet` settles end-to-end this slice. */
export type PaymentGateway = "khalti" | "esewa" | "stripe" | "wallet";

/** Payment lifecycle (`PaymentStatus`). */
export type PaymentStatus = "pending" | "success" | "failed" | "refunded";

/** Wallet ledger entry kind (`WalletTxnKind`). */
export type WalletTxnKind = "credit" | "debit";

/** A purchased ride ticket (`TicketSerializer`). `fare` is a decimal STRING. */
export interface Ticket {
  id: number;
  passenger: number;
  trip: number;
  route_name: string;
  /** Signed QR token to render as a QR code. */
  qr_code: string;
  status: TicketStatus;
  /** Decimal string, e.g. "25.00". */
  fare: string;
  payment_status: PaymentStatus;
  gateway: PaymentGateway;
  created_at: string;
}

/** An append-only wallet ledger row (`WalletTransactionSerializer`). Amounts are decimal STRINGS. */
export interface WalletTransaction {
  id: number;
  kind: WalletTxnKind;
  /** Positive magnitude, decimal string. */
  amount: string;
  /** Balance snapshot after this row, decimal string. */
  balance_after: string;
  /** Free-form origin, e.g. "ticket:123" or "refund:123". */
  reference: string;
  /** Linked payment id, or null. */
  payment: number | null;
  created_at: string;
}

/** The checkout descriptor returned by `POST /payments/checkout/`. */
export interface CheckoutResult {
  txn_ref: string;
  gateway: PaymentGateway;
  status: PaymentStatus;
  checkout_ref: string | null;
}

// ── Notifications (P5) ────────────────────────────────────────────────────────

/** Notification kinds (`NotificationType`). */
export type NotificationType =
  | "bus_arriving"
  | "route_delay"
  | "emergency"
  | "maintenance_due"
  | "trip_completed";

/**
 * An in-app notification (`NotificationSerializer`). Named `AppNotification` to avoid
 * clashing with the DOM `Notification` global. `read_at` is null while unread;
 * `payload_json` is free-form, type-specific data (e.g. `{ trip_id, route_name }`).
 */
export interface AppNotification {
  id: number;
  type: NotificationType;
  payload_json: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

// ── Admin analytics (P6) ──────────────────────────────────────────────────────

/**
 * Admin operations KPIs (`KpiSerializer`, `GET /admin/overview/kpis/`).
 *
 * All counts are integers. `revenue` is a decimal money STRING (e.g. "35.00") — keep
 * it a string and only `parseFloat` for display via `formatMoney`. `avg_delay` is
 * minutes (1dp) over today's completed trips, or `null` when there are none.
 *
 * `active_buses` = distinct buses on an in-progress trip (live ops), distinct from
 * `buses_active` = `Bus.status === "active"` fleet composition. The `*_today` trip
 * counts are scoped to the admin's local day; the bare trip counts are lifetime.
 */
export interface AdminKpis {
  // Fleet
  active_buses: number;
  total_buses: number;
  buses_active: number;
  buses_idle: number;
  buses_in_maintenance: number;
  buses_retired: number;
  // Trips — lifetime
  scheduled_trips: number;
  active_trips: number;
  completed_trips: number;
  cancelled_trips: number;
  // Trips — today
  scheduled_trips_today: number;
  active_trips_today: number;
  completed_trips_today: number;
  cancelled_trips_today: number;
  // Ridership / money / operations (today)
  passengers_today: number;
  revenue: string;
  avg_delay: number | null;
  open_alerts: number;
  maintenance_due: number;
  // Reference totals
  total_routes: number;
  total_drivers: number;
  verified_drivers: number;
}
