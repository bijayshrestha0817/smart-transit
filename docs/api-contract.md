# API Contract — Smart Transit AI

> The wire contract for the backend: conventions, the response envelope, auth, every
> `/api/v1` REST endpoint, the AI endpoints, and the WebSocket channels. Generated docs
> (drf-spectacular → Swagger) live at `/api/docs/`; **this file is the human-readable
> source of truth** the implementation must satisfy.

---

## 1. Conventions

| Aspect | Rule |
|--------|------|
| **Base path** | `/api/v1/` (URL versioning; `/api/v2/` reserved) |
| **Format** | JSON in, JSON out |
| **Envelope** | every response is `{ data, meta, errors }` (see §2) |
| **Auth** | Bearer JWT via **HttpOnly cookie** (access); see §3 |
| **Pagination** | **cursor-based default**, offset fallback (`?page=`) |
| **Filtering/Search** | `django-filter` + DRF `SearchFilter` on all list endpoints |
| **Ordering** | `?ordering=field` / `-field` |
| **Rate limits** | 100/min passenger · 300/min driver · 500/min admin · stricter anon on auth |
| **Idempotency** | payment webhooks keyed on `txn_ref`; mutations safe to retry where noted |
| **Docs** | Swagger UI `/api/docs/`, schema `/api/schema/` (drf-spectacular) |

---

## 2. Response envelope

**Success (single):**
```json
{
  "data": { "id": 42, "name": "Route 11 — Ring Road" },
  "meta": null,
  "errors": null
}
```

**Success (list, cursor-paginated):**
```json
{
  "data": [ { "id": 1 }, { "id": 2 } ],
  "meta": {
    "pagination": {
      "next": "https://api/.../?cursor=cD0yMDI2",
      "prev": null,
      "page_size": 20
    }
  },
  "errors": null
}
```

**Error:**
```json
{
  "data": null,
  "meta": null,
  "errors": [
    { "code": "validation_error", "field": "email", "detail": "Enter a valid email address." }
  ]
}
```

- HTTP status still carries semantics (`200/201/204`, `400/401/403/404/409/422`, `429`, `5xx`).
- Implemented once via a custom DRF **renderer** (wraps `data`/`meta`) + **exception
  handler** (shapes `errors`), so views never assemble the envelope by hand.

---

## 3. Auth

All tokens are delivered as **HttpOnly · Secure · SameSite=Strict cookies** — never in
the body, never in `localStorage`.

| Method | Path | Body | Result |
|--------|------|------|--------|
| `POST` | `/auth/register/` | `email, password, full_name, phone` | 201; sends verification email |
| `POST` | `/auth/verify-email/` | `token` | 200; sets `is_verified` |
| `POST` | `/auth/login/` | `email, password` | 200; sets `access`(15m)+`refresh`(7d) cookies |
| `POST` | `/auth/refresh/` | — (refresh cookie) | 200; **rotates** refresh, blacklists old |
| `POST` | `/auth/logout/` | — | 204; blacklists refresh, clears cookies |
| `POST` | `/auth/forgot-password/` | `email` | 200; sends reset link |
| `POST` | `/auth/reset-password/` | `token, new_password` | 200 |
| `GET`  | `/auth/me/` | — | 200; current user + role |

**Roles:** `passenger` · `driver` · `admin`. Every protected endpoint declares a role
permission class; the role-column on `users` is the single source of authority.

---

## 4. Passenger-facing endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/routes/` | any | list/search routes (`?search=`, filter by area) |
| `GET` | `/routes/{id}/` | any | route detail + ordered stops + polyline |
| `GET` | `/stops/` | any | list/search bus stops (`?near=lat,lng&radius=`) |
| `GET` | `/stops/{id}/` | any | stop detail + routes serving it |
| `GET` | `/trips/active/?route={id}` | passenger | active trips (buses) on a route, with last position |
| `GET` | `/trips/{id}/eta/?stop={id}` | passenger | traffic-aware + AI ETA to a stop |
| `GET` | `/favorites/` | passenger | saved routes |
| `POST`/`DELETE` | `/favorites/` `/favorites/{id}/` | passenger | save/remove favorite (optimistic) |
| `GET` | `/history/trips/` | passenger | trip history (cursor) |
| `GET` | `/tickets/` | passenger | my tickets (filter by `status`) |
| `POST` | `/tickets/` | passenger | issue ticket for a trip → returns `qr_code` |
| `GET` | `/tickets/{id}/` | passenger | ticket detail + QR payload |
| `POST` | `/tickets/{id}/refund/` | passenger | request refund |
| `GET` | `/wallet/` | passenger | balance |
| `GET` | `/wallet/transactions/` | passenger | wallet ledger (cursor) |
| `POST` | `/payments/checkout/` | passenger | start gateway payment (khalti/esewa/stripe/wallet) |
| `POST` | `/payments/webhook/{gateway}/` | gateway (signed) | confirm payment (idempotent on `txn_ref`) |
| `GET` | `/notifications/` | any | in-app feed (filter `?unread=true`) |
| `POST` | `/notifications/{id}/read/` | any | mark read |
| `POST` | `/notifications/read-all/` | any | mark all read |
| `POST` | `/emergency/report/` | passenger | file an emergency/incident |

---

## 5. Driver-facing endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/driver/shift/today/` | driver | today's assigned trips + summary |
| `GET` | `/driver/trips/{id}/` | driver | trip detail + route navigation data |
| `POST` | `/driver/trips/{id}/start/` | driver | start trip → `status=in_progress` |
| `POST` | `/driver/trips/{id}/end/` | driver | end trip → `status=completed`, emits `TRIP_COMPLETED` |
| `POST` | `/driver/trips/{id}/passenger-count/` | driver | manual/auto-suggest count |
| `POST` | `/driver/logs/` | driver | delay / breakdown / fuel / note log |
| `POST` | `/driver/sos/` | driver | **SOS** → real-time `alerts.admin` broadcast |
| `GET` | `/driver/summary/?date=` | driver | daily trip summary |

> GPS is **not** a REST endpoint on the hot path — drivers stream it over WebSocket
> (§8). A REST `POST /driver/trips/{id}/gps/batch/` exists only for **offline-queue flush**
> (buffered points uploaded on reconnect).

---

## 6. Admin endpoints

**Overview**
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/admin/overview/kpis/` | active buses, passengers today, avg delay, revenue |
| `GET` | `/admin/fleet/` | all active buses + last position (seed for the live map) |

**Management (full CRUD — `GET list`, `POST`, `GET/{id}`, `PATCH/{id}`, `DELETE/{id}` soft):**
| Resource | Path | Extra actions |
|----------|------|---------------|
| Routes | `/admin/routes/` | `POST /{id}/stops/` assign stops, `PATCH /{id}/schedule/` |
| Buses | `/admin/buses/` | `PATCH /{id}/assign-driver/`, `PATCH /{id}/maintenance/` |
| Trips | `/admin/trips/` | — (P2 minimal scheduling: `bus`+`route`+`driver`+`status`) |
| Drivers | `/admin/drivers/` | `GET /{id}/performance/`, `GET /{id}/shifts/` |
| Passengers | `/admin/passengers/` | `POST /{id}/suspend/`, `GET /{id}/history/` |
| Maintenance | `/admin/maintenance-logs/` | — |

**Analytics (feed Recharts; backed by `analytics_snapshots`):**
| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/admin/analytics/passengers-daily/` | line series |
| `GET` | `/admin/analytics/buses-hourly/` | bar series |
| `GET` | `/admin/analytics/delays-by-route/` | bar series |
| `GET` | `/admin/analytics/peak-heatmap/` | hour×day matrix |
| `GET` | `/admin/analytics/revenue/` | area series |
| `GET` | `/admin/analytics/driver-leaderboard/` | ranked table (virtualized) |
| `GET` | `/admin/analytics/fuel-by-bus/` | grouped bar |
| `GET` | `/admin/analytics/route-efficiency/` | score per route |

**Monitoring & exports:**
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/admin/alerts/` | incident log (filter by `severity`, cursor) |
| `GET` | `/admin/anomalies/` | route-deviation / overspeed feed |
| `GET` | `/admin/ai/route-suggestions/` | AI optimization suggestions panel |
| `GET` | `/admin/reports/{report}/export/?format=pdf\|csv\|xlsx` | export any report |

All admin list endpoints support `?search=`, `django-filter` params, `?ordering=`, and
cursor pagination.

---

## 7. AI endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| `POST` | `/ai/eta/` | `route_id, segment, time, occupancy, weather?` | `{ eta_minutes, arrival_time, confidence_interval:[lo,hi], model_version }` |
| `POST` | `/ai/occupancy/` | `route_id, time, day_of_week` | `{ level: "LOW\|MEDIUM\|HIGH", score, model_version }` |
| `POST` | `/ai/route-optimize/` | `route_id, traffic, demand, fuel` | `{ suggestions: [ { route, score, eta_delta, reason } ] }` |

- **Anomaly detection (D)** and **predictive maintenance (E)** are **not** request/response —
  they run as Celery jobs (anomaly polls every 30 s → WS `alerts.admin`; maintenance runs
  nightly → `MAINTENANCE_DUE` notifications). Their *outputs* surface via
  `/admin/anomalies/`, `/admin/alerts/`, and the notifications feed.
- Each AI response carries `model_version` for traceability. On model-unavailable, ETA
  falls back to Google Directions; occupancy to last-known/`MEDIUM` (architecture §5).

---

## 8. WebSocket channels

ASGI base path `/ws/`. **JWT validated on `connect`** (cookie or `?token=`); failure →
`close(4401)`. Reconnect is client-side with exponential backoff + heartbeat.

| Channel | Direction | Who | Payload |
|---------|-----------|-----|---------|
| `/ws/trip/{trip_id}/` | server → passenger | passenger viewing a bus | `{ lat, lng, speed, heading, ts }` every 3–5 s |
| `/ws/driver/{trip_id}/` | driver → server | the trip's driver | GPS emit in; ack/heartbeat out |
| `/ws/fleet/` | server → admin | admin | all active-bus positions (overview map) |
| `/ws/alerts/` | server → admin | admin | anomalies, SOS, deviations (severity-tagged) |
| `/ws/notifications/` | server → user | any authed | in-app notifications (mirrors feed) |

**Geofencing** ("bus 2 stops away → `BUS_ARRIVING`") is computed server-side on inbound
GPS against `bus_stops.sequence`, then pushed to the relevant passengers' notification
channel — the client does not poll.

---

## 9. Status codes & errors

| Code | When |
|------|------|
| `400` | malformed request |
| `401` | missing/expired access token (client should hit `/auth/refresh/`) |
| `403` | authenticated but wrong role / not owner |
| `404` | not found (or soft-deleted) |
| `409` | conflict (e.g. starting an already-started trip) |
| `422` | semantic validation failure |
| `429` | rate limit exceeded (includes `Retry-After`) |
| `5xx` | server error (enveloped, no stack traces leaked) |

Error `code`s are stable machine strings (`validation_error`, `not_verified`,
`insufficient_balance`, `payment_failed`, `trip_already_started`, `trip_not_in_progress`,
`trip_not_assigned`, …) so the frontend can branch on them without parsing prose.
