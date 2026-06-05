# Data Model & ER Diagram — Smart Transit AI

> PostgreSQL schema for the 12 core tables plus the wallet ledger (`wallets`,
> `wallet_transactions`, added with P4). Every table inherits the base fields
> `created_at`, `updated_at`, `is_deleted` (soft delete). Conventions and indexing
> strategy follow the diagram. Target ORM: **Django 6** models.

---

## 1. Conventions

- **Base model.** All tables extend an abstract `TimeStampedSoftDeleteModel`:
  `id` (BigAuto PK), `created_at` (auto), `updated_at` (auto), `is_deleted` (bool,
  default `false`). The default manager filters `is_deleted=False`; an `all_objects`
  manager exposes soft-deleted rows for admin/audit.
- **Keys.** Surrogate `BigAutoField` PKs everywhere. FKs use `on_delete=PROTECT` for
  reference data (route, bus) and `CASCADE`/`SET_NULL` only where a child truly cannot
  outlive its parent — chosen per relationship below.
- **Money.** `DECIMAL(10,2)`, never float. **Timestamps** are `timestamptz` (UTC).
  **Coordinates** are `DECIMAL(9,6)` (≈ 0.11 m precision) — sufficient and index-friendly.
- **Enums** are Django `TextChoices` (stored as short `varchar`, validated in app +
  optional DB `CHECK`).

---

## 2. ER diagram

```mermaid
erDiagram
    USERS ||--o{ BUSES            : "drives (assigned_driver)"
    USERS ||--o{ TRIPS            : "drives"
    USERS ||--o{ TICKETS          : "buys (passenger)"
    USERS ||--|| WALLETS          : "has (store credit)"
    USERS ||--o{ NOTIFICATIONS    : "receives"
    USERS ||--o{ DRIVER_LOGS      : "authors"

    ROUTES ||--o{ BUS_STOPS       : "has"
    ROUTES ||--o{ TRIPS           : "scheduled on"

    BUSES  ||--o{ TRIPS           : "runs"
    BUSES  ||--o{ MAINTENANCE_LOGS: "serviced in"

    TRIPS  ||--o{ GPS_LOCATIONS   : "emits"
    TRIPS  ||--o{ TICKETS         : "sold for"
    TRIPS  ||--o{ DRIVER_LOGS     : "logged during"

    TICKETS ||--|| PAYMENTS       : "paid by"

    WALLETS ||--o{ WALLET_TRANSACTIONS : "ledger of"
    PAYMENTS ||--o{ WALLET_TRANSACTIONS : "settles/refunds via"

    USERS {
        bigint   id PK
        string   role "enum: passenger|driver|admin"
        citext   email UK
        string   hashed_password
        bool     is_verified
        string   full_name
        string   phone
        timestamptz created_at
        timestamptz updated_at
        bool     is_deleted
    }
    BUSES {
        bigint   id PK
        string   plate UK
        int      capacity
        string   status "enum: active|idle|maintenance|retired"
        bigint   assigned_driver_id FK "→ users.id (role=driver), nullable"
    }
    ROUTES {
        bigint   id PK
        string   name
        jsonb    polyline_json
        int      estimated_duration "minutes"
        string   color "hex, for map polyline"
        decimal  fare "DECIMAL(8,2), >= 0.01 (P4 ticket price)"
    }
    BUS_STOPS {
        bigint   id PK
        string   name
        decimal  lat
        decimal  lng
        bigint   route_id FK "→ routes.id"
        int      sequence "order along route"
    }
    TRIPS {
        bigint   id PK
        bigint   bus_id FK
        bigint   route_id FK
        bigint   driver_id FK "→ users.id"
        timestamptz start_time "nullable, set on start"
        timestamptz end_time "nullable, set on end"
        string   status "enum: scheduled|in_progress|completed|cancelled"
        int      passenger_count "nullable, driver-entered (P2)"
    }
    GPS_LOCATIONS {
        bigint   id PK
        bigint   trip_id FK
        decimal  lat
        decimal  lng
        decimal  speed "km/h"
        decimal  heading "deg, nullable"
        timestamptz timestamp "INDEXED"
    }
    TICKETS {
        bigint   id PK
        bigint   passenger_id FK "→ users.id"
        bigint   trip_id FK
        string   qr_code UK
        string   status "enum: issued|active|used|expired|refunded|cancelled"
        decimal  fare
    }
    PAYMENTS {
        bigint   id PK
        bigint   ticket_id FK UK
        decimal  amount
        string   gateway "enum: khalti|esewa|stripe|wallet"
        string   status "enum: pending|success|failed|refunded"
        string   txn_ref UK
    }
    WALLETS {
        bigint   id PK
        bigint   user_id FK UK "→ users.id (one per user)"
        decimal  balance "DECIMAL(12,2), default 0, source of truth"
    }
    WALLET_TRANSACTIONS {
        bigint   id PK
        bigint   wallet_id FK
        string   kind "enum: credit|debit"
        decimal  amount "DECIMAL(12,2), positive magnitude"
        decimal  balance_after "snapshot after applying"
        bigint   payment_id FK "→ payments.id, nullable (SET_NULL)"
        string   reference "e.g. ticket:123 | refund:123"
    }
    NOTIFICATIONS {
        bigint   id PK
        bigint   user_id FK
        string   type "enum: BUS_ARRIVING|ROUTE_DELAY|EMERGENCY|MAINTENANCE_DUE|TRIP_COMPLETED"
        jsonb    payload_json
        timestamptz read_at "nullable"
    }
    DRIVER_LOGS {
        bigint   id PK
        bigint   driver_id FK
        bigint   trip_id FK "nullable"
        string   event_type "enum: delay|breakdown|fuel|sos|note"
        text     notes
        timestamptz timestamp
    }
    MAINTENANCE_LOGS {
        bigint   id PK
        bigint   bus_id FK
        string   service_type
        decimal  cost
        timestamptz serviced_at
        date     next_due
    }
    ANALYTICS_SNAPSHOTS {
        bigint   id PK
        string   snapshot_type "enum: daily_passengers|hourly_buses|route_delay|revenue|..."
        jsonb    data_json
        timestamptz period_start
        timestamptz period_end
    }
```

---

## 3. Table reference

### `users`
Custom Django user (email login, no username). `role` drives RBAC across the whole API.
Passwords hashed with Django's PBKDF2/Argon2. `is_verified` gates login until email
confirmation.

| Field | Type | Notes |
|-------|------|-------|
| `role` | enum | `passenger` \| `driver` \| `admin` |
| `email` | citext | unique, case-insensitive |
| `hashed_password` | varchar | Django hasher |
| `is_verified` | bool | email verification gate |

### `buses`
`assigned_driver_id` → `users` (nullable, `SET_NULL` — a bus survives driver reassignment).
`status` color-codes the admin fleet map.

### `routes`
`polyline_json` stores the encoded/decoded path for map rendering; `color` drives the
per-route polyline. `estimated_duration` is the static baseline the AI ETA refines.
`fare` (P4) is the server-authoritative ticket price (`DECIMAL(8,2)`, `>= 0.01`); a ticket
snapshots it at issue time so later price changes don't alter past sales.

### `bus_stops`
Ordered by `sequence` along a route. `(lat,lng)` feed both the map markers and the
geofencing "N stops away" calculation.

### `trips`
The operational heart: a `bus` + `route` + `driver` over a time window. `status`
transitions `scheduled → in_progress → completed` (or `cancelled`). Almost every live and
analytical query joins through here. `passenger_count` (nullable) is the driver-entered
manual count from `POST /driver/trips/{id}/passenger-count/` (added in P2; AI occupancy is P5).

### `gps_locations`
**Highest-volume table** (one row per emit, every 3–5 s per active trip). Append-only,
never updated. `timestamp` is indexed; the composite `(trip_id, timestamp)` index serves
both live "latest position for trip" and historical playback. See §5 for scaling.

### `tickets`
`qr_code` is a unique, signed token (not the raw PK) scanned on boarding. `status`
lifecycle covers issuance through refund. One ticket ↔ one payment.

### `payments`
One-to-one with `tickets` (`ticket_id` unique). `gateway` includes `wallet` for in-app
balance spends. `txn_ref` is the gateway's reference, unique for idempotent webhook
handling (partial-unique `WHERE is_deleted=false`). `amount` is `DECIMAL(8,2)` (= ticket fare).

### `wallets` (P4)
One row per user (`user_id` unique), `balance DECIMAL(12,2)` is the store-credit source of
truth — mutated only under `SELECT … FOR UPDATE` so concurrent debits/credits serialize.
Funded by **refunds** (store credit); external top-up is future/D4 (no top-up endpoint yet).

### `wallet_transactions` (P4)
Append-only ledger. Each row is a `credit`/`debit` of a positive `amount` with a
`balance_after` snapshot, an optional `payment_id` link, and a `reference` (`ticket:<id>` /
`refund:<id>`). Written in the same transaction as the balance change.

### `notifications`
In-app feed + FCM/email fan-out source. `payload_json` carries type-specific data
(bus id, ETA, incident). `read_at` null = unread.

### `driver_logs`
Audit + operational events authored by drivers (delay, breakdown, fuel, **sos**, note).
`event_type=sos` triggers the real-time admin emergency alert.

### `maintenance_logs`
Service history per bus; `next_due` feeds the predictive-maintenance `MAINTENANCE_DUE`
nightly check.

### `analytics_snapshots`
Pre-aggregated rollups produced by Celery so dashboard charts read one row instead of
scanning raw tables. `data_json` shape varies by `snapshot_type`; `period_*` bound the window.

---

## 4. Indexing strategy

Driven by the read patterns in [`api-contract.md`](api-contract.md) and the
**p95 < 200 ms** target.

| Index | Table | Purpose |
|-------|-------|---------|
| `(trip_id, timestamp DESC)` | `gps_locations` | latest position per trip + playback (the hot path) |
| `(timestamp)` | `gps_locations` | anomaly poll scanning a recent time window across trips |
| `(passenger_id)` | `tickets` | "my tickets" list |
| `(trip_id)` | `tickets` | passenger count / load per trip |
| `(gateway, status)` | `payments` | reconciliation + revenue analytics |
| `(wallet_id, -created_at)` | `wallet_transactions` | wallet ledger (cursor) |
| `(status, route_id)` | `trips` | active-trips-per-route, fleet map |
| `(route_id, sequence)` | `bus_stops` | ordered stops for a route |
| `(user_id, read_at)` | `notifications` | unread feed per user |
| `(bus_id, serviced_at)` | `maintenance_logs` | service history, next-due |
| partial `WHERE is_deleted=false` | all soft-deletable | keep indexes lean (don't index tombstones) |
| `email` unique | `users` | login lookup |
| `qr_code`, `txn_ref` unique | `tickets`, `payments` | scan + idempotency |

---

## 5. Scaling & integrity notes

- **`gps_locations` growth.** At ~1 row / 4 s, 100 active buses ≈ 2.16 M rows/day. Plan:
  (1) **range-partition by `timestamp`** (monthly) so old partitions detach/archive cheaply;
  (2) keep only a hot window in Postgres, roll the rest to cold storage; (3) if volume
  outpaces this, evaluate **TimescaleDB** (hypertable) — an extension, not a schema rewrite.
  *(Decision deferred to implementation — see architecture §9.)*
- **Soft delete + uniqueness.** Unique constraints (`email`, `plate`, `qr_code`) must
  account for tombstones — use partial unique indexes `WHERE is_deleted=false` so a deleted
  row doesn't block reuse.
- **Referential safety.** `trips` PROTECTs `bus`/`route` (can't delete reference data with
  history); `gps_locations`/`tickets` CASCADE from a hard-deleted trip only — but trips are
  soft-deleted in practice, so cascades are rare.
- **Money correctness.** `payments.amount` and `tickets.fare` are `DECIMAL`; all monetary
  math in Python uses `Decimal`, never float.
- **Time zones.** Everything `timestamptz` in UTC; presentation converts at the edge.
