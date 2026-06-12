# Project Context (maintained by zero)

Updated: 2026-06-11
Branch: main

## Stack
- **Backend:** Python 3.13 (CI runs 3.12), Django 6.0, DRF 3.17, django-filter, SimpleJWT
  (rotation + blacklist), drf-spectacular (Swagger at `/api/docs/`).
- **Realtime:** Django Channels 4.3 + channels-redis, Daphne (ASGI). Consumers live in
  top-level `realtime/`.
- **Async:** Celery 5.6 + Redis (broker/cache/channel layer). `config/celery.py`;
  `CELERY_BEAT_SCHEDULE` is empty (populated in P5).
- **DB:** PostgreSQL 17 (psycopg 3). Tests use in-memory SQLite + locmem + in-memory
  channel layer (no services needed).
- **Auth hashing:** argon2.
- **Frontend:** Next.js 16 (App Router, React 19, TS), Tailwind v4 + ShadCN, TanStack
  Query/Table/Form, Zustand, Zod, Axios (cookie-aware, 401→refresh). Tests via Vitest + MSW.
- **Tooling:** ruff (lint + format, line-length 100, py312 target). pytest + pytest-django
  + pytest-asyncio + factory-boy.

## Architecture / Flow
Layered, per CLAUDE.md: **URL → View → Service → Repository → Model**.
- Views never touch the ORM; **all ORM access lives in repositories** (one class per model,
  static/class methods, soft-delete aware via `BaseRepository`). `apps/common/repository/base.py`.
- Services hold business rules; raise `CustomException` (subclass of DRF `APIException`,
  `apps/common/exceptions.py`).
- **Response envelope** `{data, meta, errors}`:
  - `CustomResponse` (`apps/common/response.py`) builds it explicitly; tags `__enveloped__`.
  - `EnvelopeJSONRenderer` (`apps/common/renderers.py`) wraps plain `Response`, lifts
    paginated payloads, passes through pre-enveloped ones.
  - `envelope_exception_handler` flattens DRF errors to `[{code, field, detail}]`.
- **Soft delete + timestamps:** `TimeStampedSoftDeleteModel` (`apps/common/models.py`).
  `objects` hides soft-deleted; `all_objects` is the escape hatch. `.delete()` flags `is_deleted`.
- **Pagination:** `DefaultCursorPagination` (default, `-created_at`, page_size 20/max 100);
  `OffsetFallbackPagination` for admin tables. Both tag `__paginated__`.
- **RBAC:** `apps/common/permissions.py` — `IsPassenger / IsDriver / IsAdmin /
  IsOwnerOrAdmin`. Every view declares a permission explicitly. Roles: passenger/driver/admin.
- **Per-app URL versioning:** root `config/urls.py` mounts each app at `/api/`; each app's
  `urls.py` dispatches to `v1/` (so public surface is `/api/v1/…`, versioning is per app).
- **Throttling:** scoped rates configured — anon 30/min, passenger 100/min, driver 300/min,
  admin 500/min.

## Modules (backend/apps/)
| Module | Models | Notes |
|--------|--------|-------|
| accounts | User | Cookie-JWT auth (HttpOnly/Secure/SameSite=Strict), register/verify/login/refresh/logout/forgot/reset/me |
| buses | Route, BusStop, Bus | Public read + admin CRUD ViewSets (routes/buses/drivers); has `management/commands` (seed) |
| trips | Trip, GpsLocation | Admin CRUD + driver lifecycle ViewSets; ActiveTrips, FleetSnapshot; GpsLocationRepository |
| payments | Ticket, Payment, Wallet, WalletTransaction | Tickets ViewSet (+refund), wallet reads, checkout, signed webhook `/payments/webhook/{gateway}/`; `gateways/` adapters |
| notifications | Notification | Feed + read/read-all; Celery `tasks.py`; signals; realtime push |
| driver_logs | DriverLog | Driver log create + SOS |
| maintenance | MaintenanceLog | Admin maintenance-log CRUD |
| common | (abstract) | Base layer described above |

`realtime/`: `consumers.py`, `broadcast.py`, `groups.py`, `middleware.py` (JWT-on-connect),
`routing.py`.

## Endpoints (all under /api/v1/)
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | auth/register, verify-email, login, refresh, logout, forgot-password, reset-password | mixed | Auth flow |
| GET | auth/me | authed | Current user |
| GET | routes/, routes/{id}, stops/, stops/{id} | public read | Reference data |
| CRUD | admin/routes, admin/buses, admin/drivers | admin | Fleet reference CRUD |
| CRUD | admin/trips, driver/trips | admin/driver | Trip lifecycle |
| GET | trips/active/ | — | Active trips |
| GET | admin/fleet/ | admin | Fleet snapshot |
| CRUD | tickets (+refund) | passenger/admin | Ticketing |
| GET | wallet/, wallet/transactions/ | passenger | Wallet |
| POST | payments/checkout/, payments/webhook/{gateway}/ | mixed | Payments |
| GET/POST | notifications/, notifications/{id}/read/, notifications/read-all/ | authed | Notifications |
| POST | driver/logs/, driver/sos/ | driver | Driver logs / SOS |
| CRUD | admin/maintenance-logs | admin | Maintenance |
| — | api/schema/, api/docs/ | — | OpenAPI + Swagger |

## Conventions & Boundaries
- PascalCase repository filenames (e.g. `TripRepository.py`, `GpsLocationRepository.py`).
- Query-shaping (`select_related`/`prefetch_related`) lives in repositories, matched to
  what serializers access.
- `Decimal` for money (payments). Webhooks idempotent on `txn_ref`.
- Tests colocated per app under `tests/` (`test_*.py`); model/service/api split.
- CI (`.github/workflows/ci.yml`): backend job = ruff check + ruff format --check +
  `manage.py check` + pytest; frontend job = eslint + tsc + vitest + next build.

## Phase status (docs/build-plan.md, P0→P7)
- **P0 Foundation + Auth** — ✅ done
- **P1 Domain CRUD** — ✅ done
- **P2 Real-time tracking** — ✅ backend done (channels, consumers, GPS); frontend driver
  portal partially scaffolded
- **P3 Passenger live map** — 🟡 frontend pages scaffolded; map/animation work outstanding
- **P4 Ticketing + payments** — ✅ done (merged PR #3, 2026-06-05)
- **P5 AI modules** — ❌ not started (no `ai_modules/`, no `/ai/*` or `/trips/{id}/eta/`
  endpoints, empty `CELERY_BEAT_SCHEDULE`)
- **P6 Admin dashboard + analytics** — 🟡 frontend pages scaffolded; backend has only
  FleetSnapshot — no `/admin/overview/kpis/`, no `analytics_snapshots`
- **P7 Hardening + deploy** — ❌ not started (no health-check endpoint, no prod compose/nginx)

## Known Gaps / Backlog (ranked by value-for-effort)
1. **P6 backend — admin KPI/overview endpoint** (`/admin/overview/kpis/`) + service. High
   value for the admin dashboard, self-contained, fits the layered pattern. Medium effort.
2. **P5 — baseline ETA endpoint** (`/trips/{id}/eta/` or `/ai/eta/`) with a heuristic +
   graceful fallback, before the full ML pipeline. Unblocks P3 ETA display. Medium effort.
3. **P7 — health-check endpoint** (`/api/health/`) + Django/DB/Redis probes. Low effort,
   needed for deploy/uptime.
4. **CI Python version** — CI uses 3.12 but README/runtime target 3.13. Low effort, align.
5. **P5 — Celery anomaly poll + predictive maintenance** (populate `CELERY_BEAT_SCHEDULE`).
   Larger; depends on AI groundwork.
