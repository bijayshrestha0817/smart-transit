# Smart Transit AI — Backend

> Django 6 + DRF API for an intelligent public-transportation platform: live bus tracking,
> AI-predicted ETAs & occupancy, digital ticketing, and a real-time operations dashboard.

This is the **backend** service. It speaks two protocols from one codebase: a synchronous
REST API (DRF over WSGI/Gunicorn) and a real-time WebSocket layer (Django Channels over
ASGI/Daphne), with Celery workers for background and scheduled jobs. Everything is wired
behind a single, consistent `{data, meta, errors}` response envelope.

**Implementation status:** Phases **P0 (foundation + auth)** and **P1 (domain CRUD)** are
complete and tested. Real-time tracking (P2), ticketing (P4), and AI serving (P5) are
scaffolded but not yet implemented — the ASGI app, Channel layer, and Celery app boot
today with empty routing/schedules so later phases only register handlers. See the
[Roadmap](#roadmap) and the repo-level [`docs/build-plan.md`](../docs/build-plan.md).

---

## Table of contents

- [At a glance](#at-a-glance)
- [Tech stack & versions](#tech-stack--versions)
- [Architecture: layered View → Service → Repository](#architecture-layered-view--service--repository)
- [Project layout](#project-layout)
- [The response envelope](#the-response-envelope)
- [Authentication & authorization](#authentication--authorization)
- [Apps reference](#apps-reference)
- [Data model](#data-model)
- [API reference](#api-reference)
- [Pagination, filtering, search & ordering](#pagination-filtering-search--ordering)
- [Error handling & domain exceptions](#error-handling--domain-exceptions)
- [Configuration & environment variables](#configuration--environment-variables)
- [Getting started](#getting-started)
- [Database, migrations & seed data](#database-migrations--seed-data)
- [Testing](#testing)
- [Code quality & conventions](#code-quality--conventions)
- [OpenAPI / Swagger](#openapi--swagger)
- [Processes & ports](#processes--ports)
- [Roadmap](#roadmap)
- [Related documentation](#related-documentation)

---

## At a glance

| | |
|---|---|
| **Framework** | Django 6.0 + Django REST Framework 3.17 |
| **Python** | 3.13 (Docker image) · 3.12 supported locally — `pyproject` targets `py312` |
| **Database** | PostgreSQL 17 (psycopg 3) |
| **Cache / broker / channel layer** | Redis 7 (one instance, three jobs) |
| **Real-time** | Django Channels 4.3 (Daphne ASGI) — wired, consumers land in P2 |
| **Background jobs** | Celery 5.6 + Celery Beat — wired, schedule populated in P5 |
| **Auth** | SimpleJWT in HttpOnly·SameSite=Strict cookies; Argon2 hashing |
| **API docs** | drf-spectacular → OpenAPI 3 at `/api/schema/`, Swagger UI at `/api/docs/` |
| **Response shape** | Uniform `{data, meta, errors}` envelope on every response |
| **Tests** | 35 passing (pytest + pytest-django) |
| **Lint/format** | Ruff |

---

## Tech stack & versions

Pinned in [`requirements/base.txt`](requirements/base.txt) (+ `dev.txt` / `prod.txt`). Versions
reflect the latest stable verified for the project (see the repo-root [`README.md`](../README.md)
version table). Celery 5.6 caps the runtime at Python ≤ 3.13, which is why the image is 3.13.

**Runtime (base.txt)**

| Package | Pin | Role |
|---------|-----|------|
| `Django` | `>=6.0,<6.1` | Web framework |
| `djangorestframework` | `>=3.17,<3.18` | REST API toolkit |
| `django-filter` | `>=25.1` | Declarative query filtering |
| `djangorestframework-simplejwt` | `>=5.5,<6.0` | JWT access/refresh, rotation, blacklist |
| `drf-spectacular` | `>=0.28` | OpenAPI 3 schema → Swagger UI |
| `channels` | `>=4.3,<4.4` | WebSockets / ASGI |
| `channels-redis` | `>=4.2` | Redis-backed channel layer |
| `daphne` | `>=4.1` | ASGI server |
| `celery` | `>=5.6,<5.7` | Async task queue |
| `redis` | `>=5.0,<5.3` | Redis client (Celery 5.6 caps at ≤ 5.2.1) |
| `psycopg[binary]` | `>=3.2` | PostgreSQL adapter (psycopg 3, manylinux wheels) |
| `argon2-cffi` | `>=23.1` | Argon2 password hasher |
| `django-environ` | `>=0.11` | 12-factor env config |
| `django-cors-headers` | `>=4.6` | CORS for the SPA frontend |

**Dev (dev.txt):** `pytest`, `pytest-django`, `pytest-asyncio` (async consumer tests),
`factory-boy`, `ruff`.
**Prod (prod.txt):** `gunicorn` (WSGI HTTP), `whitenoise` (static behind Nginx).

---

## Architecture: layered View → Service → Repository

The backend follows a strict **layered architecture**. Each layer has one job and only
talks to the layer directly below it. This keeps HTTP concerns, business rules, and data
access independent and testable.

```
HTTP request
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ View          apps/<app>/v1/views/*.py                            │
│  · HTTP + cookie mechanics, status codes                          │
│  · validates input with a Serializer                              │
│  · calls a Service, wraps the result in CustomResponse            │
│  · declares permission_classes (RBAC) — never queries the ORM     │
└─────────────────────────────────────────────────────────────────┘
    │ validated_data
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Service       apps/<app>/v1/service/*.py                          │
│  · business rules, multi-step orchestration                      │
│  · wraps mutations in transaction.atomic()                        │
│  · raises domain exceptions (CustomException subclasses)          │
│  · calls Repositories — never touches the ORM directly            │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Repository    apps/<app>/repository/*.py                          │
│  · the ONLY place ORM queries live (one class per model)          │
│  · owns select_related / prefetch_related (kills N+1 here)        │
│  · soft-delete aware; returns querysets / instances / None        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Model         apps/<app>/models.py                                │
│  · schema, constraints, soft delete, __str__                      │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
            CustomResponse / EnvelopeJSONRenderer
            → {data, meta, errors} on the wire
```

**The rules that hold the layers apart** (enforced by review and captured in
[`.claude/skills/django-expert/GOTCHAS.md`](../.claude/skills/django-expert/GOTCHAS.md)):

1. **Views never query the ORM.** They validate, call a service, and shape a response.
2. **Services never query the ORM directly.** They call repository methods and own transactions.
3. **Repositories are the only ORM holders.** One class per model; they own `select_related`/
   `prefetch_related` so N+1 problems are fixed at the data layer, not patched in serializers.
4. **Serializers don't touch the ORM either.** Uniqueness/lookups go through a repository method
   (e.g. `BusRepository.plate_exists(...)`).
5. **The envelope is never hand-built.** Success → `CustomResponse`; errors → `CustomException`
   or `serializers.ValidationError` → `envelope_exception_handler`.

### API versioning

Versioning lives **per app**. The root URLconf mounts each app under `/api/`, and each app's
`urls.py` dispatches to a versioned sub-package (`v1/`, later `v2/`). The public surface stays
`/api/v1/…` while each app owns its own version timeline.

```
config/urls.py  ──include──▶  apps.accounts.urls  ──include──▶  apps.accounts.v1.urls  (→ /api/v1/auth/…)
                ──include──▶  apps.buses.urls     ──include──▶  apps.buses.v1.urls     (→ /api/v1/…)
```

---

## Project layout

```
backend/
├── Dockerfile                 # Python 3.13-slim image, runs as unprivileged `app` user
├── .dockerignore
├── .env.example               # copy to .env for local (non-Docker) runs
├── pyproject.toml             # Ruff + pytest configuration
├── manage.py                  # defaults to config.settings.dev
├── requirements/
│   ├── base.txt               # runtime deps (shared)
│   ├── dev.txt                # + pytest, ruff, factory-boy
│   └── prod.txt               # + gunicorn, whitenoise
│
├── config/                    # project configuration (not a Django "app")
│   ├── settings/
│   │   ├── base.py            # shared settings, read from env via django-environ
│   │   ├── dev.py             # DEBUG, browsable API
│   │   ├── prod.py            # HTTPS hardening, WhiteNoise, secure cookies
│   │   └── test.py            # in-memory SQLite + locmem + fast MD5 hashing
│   ├── urls.py                # root URLconf: /admin/, /api/, /api/schema/, /api/docs/
│   ├── asgi.py                # ASGI entry (HTTP→Django, WS→Channels; WS router empty until P2)
│   ├── wsgi.py                # WSGI entry (Gunicorn, prod settings)
│   └── celery.py              # Celery app (autodiscovers apps/*/tasks.py)
│
└── apps/
    ├── common/                # shared building blocks for the layered architecture
    │   ├── models.py          # TimeStampedSoftDeleteModel (timestamps + soft delete)
    │   ├── repository/base.py # BaseRepository (soft-delete-aware data-access helpers)
    │   ├── response.py        # CustomResponse — explicit envelope builder
    │   ├── renderers.py       # EnvelopeJSONRenderer — {data, meta, errors}
    │   ├── exceptions.py      # CustomException + envelope_exception_handler
    │   ├── pagination.py      # DefaultCursorPagination + OffsetFallbackPagination
    │   └── permissions.py     # IsPassenger / IsDriver / IsAdmin / IsOwnerOrAdmin
    │
    ├── accounts/              # custom User, auth flows (P0)
    │   ├── models.py          # email-login User with role-based RBAC + soft delete
    │   ├── managers.py        # UserManager (email identifier, createsuperuser)
    │   ├── enums.py           # UserRole (passenger / driver / admin)
    │   ├── authentication.py  # CookieJWTAuthentication (cookie OR Bearer header)
    │   ├── tokens.py          # signed email-verify / password-reset tokens (no DB table)
    │   ├── exceptions.py      # InvalidCredentialsError, EmailNotVerifiedError
    │   ├── schema.py          # drf-spectacular security scheme for the cookie auth
    │   ├── admin.py
    │   ├── urls.py            # → v1/auth/
    │   ├── repository/AccountRepository.py
    │   ├── v1/
    │   │   ├── urls.py
    │   │   ├── views/         # AuthViews.py, MeViews.py
    │   │   ├── service/       # AuthService.py
    │   │   └── serializers/   # AuthSerializer.py, UserSerializer.py
    │   └── tests/test_auth.py
    │
    └── buses/                 # routes, stops, fleet, drivers (P1)
        ├── models.py          # Route, BusStop, Bus
        ├── enums.py           # BusStatus (active / idle / maintenance / retired)
        ├── exceptions.py      # DriverNotFoundError
        ├── admin.py
        ├── urls.py            # → v1/
        ├── management/commands/seed_demo.py   # idempotent Kathmandu demo seed
        ├── repository/        # RouteRepository, BusStopRepository, BusRepository, DriverRepository
        ├── v1/
        │   ├── urls.py        # public routes/stops + admin router (routes/buses/drivers)
        │   ├── views/         # RouteViews, StopViews, BusViews, DriverViews
        │   ├── service/       # RouteService, BusService, DriverService
        │   └── serializers/   # Route / BusStop / Bus / Driver serializers
        └── tests/             # test_models, test_routes_api, test_stops_api, test_admin_api
```

> **File-naming convention:** view/service/serializer/repository **modules are PascalCase**
> and named after their primary class (`AuthService.py`, `BusRepository.py`,
> `RouteSerializer.py`). Each `__init__.py` re-exports the public classes so imports stay
> `from apps.buses.v1.service import RouteService`.

---

## The response envelope

Every API response — success or error, single or paginated — has the same three top-level keys:

```jsonc
{ "data": <payload|null>, "meta": <object|null>, "errors": <array|null> }
```

| Case | `data` | `meta` | `errors` |
|------|--------|--------|----------|
| Success (single) | the object | `null` (or `{"message": "…"}`) | `null` |
| Success (paginated) | array of objects | `{"pagination": {…}}` | `null` |
| Error | `null` | `null` | `[{code, field, detail}, …]` |

**How it's produced (two mechanisms, one shape):**

- **`CustomResponse`** ([`apps/common/response.py`](apps/common/response.py)) — views build success
  responses explicitly. It tags the payload `__enveloped__` and lets an optional `message` ride in
  `meta`. Example: `return CustomResponse(UserSerializer(user).data, status=201)`.
- **`EnvelopeJSONRenderer`** ([`apps/common/renderers.py`](apps/common/renderers.py)) — the default
  renderer. It passes through already-shaped payloads (`__enveloped__`, `__enveloped_error__`),
  lifts paginated payloads (`__paginated__`) into `data`/`meta`, and defensively wraps anything else.

**Examples**

```jsonc
// GET /api/v1/auth/me/  → 200
{ "data": { "id": 7, "email": "rider@example.com", "role": "passenger", "is_verified": true }, "meta": null, "errors": null }

// GET /api/v1/routes/  → 200 (cursor-paginated)
{ "data": [ { "id": 1, "name": "Ring Road", "color": "#1E88E5" } ],
  "meta": { "pagination": { "next": "http://…?cursor=cD0y", "prev": null, "page_size": 20 } },
  "errors": null }

// POST /api/v1/auth/login/ with a bad password → 400
{ "data": null, "meta": null, "errors": [ { "code": "invalid_credentials", "field": null, "detail": "Invalid email or password." } ] }

// POST /api/v1/auth/register/ with a weak password → 400 (field error)
{ "data": null, "meta": null, "errors": [ { "code": "password_too_short", "field": "password", "detail": "This password is too short…" } ] }
```

> **Testing note:** assert on `resp.json()` (the rendered wire shape), **not** `resp.data` (raw
> pre-render serializer output). The envelope is applied at render time.

---

## Authentication & authorization

### Cookie-delivered JWT

Tokens are issued by SimpleJWT and delivered **exclusively as HttpOnly cookies** — client
JavaScript can never read them, which closes the XSS token-theft vector.

| Setting | Value |
|---------|-------|
| Access token lifetime | 15 minutes |
| Refresh token lifetime | 7 days |
| Refresh rotation | enabled (`ROTATE_REFRESH_TOKENS`) |
| Old refresh on rotation | blacklisted (`BLACKLIST_AFTER_ROTATION`) |
| Algorithm | HS256, signed with `SECRET_KEY` |
| User id claim | `user_id`; a custom `role` claim is added on issue |
| Access cookie | `st_access` |
| Refresh cookie | `st_refresh` |
| Cookie flags | `HttpOnly`, `SameSite=Strict`, `Path=/`, `Secure` (prod only) |

[`CookieJWTAuthentication`](apps/accounts/authentication.py) is the default DRF authenticator. It
reads the JWT from the `Authorization: Bearer …` header **if present** (mobile / service-to-service),
otherwise from the `st_access` cookie (browsers). The same class is what P2's WebSocket middleware
will reuse to validate the handshake. [`schema.py`](apps/accounts/schema.py) registers a
drf-spectacular extension so OpenAPI models both modes as *alternative* security requirements.

Stateless **signed tokens** ([`tokens.py`](apps/accounts/tokens.py)) back email verification
(24 h) and password reset (1 h) without an extra DB table — distinct salts stop a verify token
from being replayed as a reset token.

### Roles & permission classes

Three roles live in [`accounts/enums.py`](apps/accounts/enums.py): `passenger` (the registration
default), `driver`, `admin`. RBAC is enforced by explicit permission classes in
[`apps/common/permissions.py`](apps/common/permissions.py):

| Class | Grants access to |
|-------|------------------|
| `IsPassenger` | users with `role == "passenger"` |
| `IsDriver` | users with `role == "driver"` |
| `IsAdmin` | users with `role == "admin"` |
| `IsOwnerOrAdmin` | admins, or the object's owner (owning field configurable via `owner_field`) |

> **Every view declares a permission class** — no endpoint ships without an intentional rule.
> Public reads use `AllowAny`; admin endpoints use `IsAdmin`.

### Throttling

Rate-limit scopes are defined in settings: `anon` 30/min, `passenger` 100/min, `driver` 300/min,
`admin` 500/min. `AnonRateThrottle` applies globally today. The role scopes use
`ScopedRateThrottle`, which is **inert until a view names it** via `throttle_scope = "admin"`
(see GOTCHAS §7) — a deliberate hook for later phases.

### Password security

Argon2 is the primary hasher (PBKDF2 / bcrypt as fallbacks). Validators enforce a minimum length
of 8, similarity, common-password, and numeric-only checks.

---

## Apps reference

### `apps.common` — shared foundation

The building blocks every domain app composes:

- **`TimeStampedSoftDeleteModel`** — abstract base adding `created_at` (indexed), `updated_at`,
  `is_deleted`. `objects` (default manager) hides soft-deleted rows; `all_objects` is the escape
  hatch. `.delete()` is overridden to **soft**-delete; `.hard_delete()` actually removes the row.
  `SoftDeleteQuerySet.delete()` soft-deletes a whole queryset.
- **`BaseRepository`** — `active()`, `get_or_none(**filters)`, and `apply_update(instance, data)`
  (the PATCH idiom using `update_fields`). Subclasses set `model` and add query methods.
- **`CustomResponse`**, **`EnvelopeJSONRenderer`**, **`CustomException` + `envelope_exception_handler`** —
  the envelope machinery (above).
- **`DefaultCursorPagination`** / **`OffsetFallbackPagination`** — see [Pagination](#pagination-filtering-search--ordering).
- **Permission classes** — see [above](#roles--permission-classes).

### `apps.accounts` — identity & auth (P0)

Custom email-login `User` model with role-based RBAC, plus the full auth flow: register →
verify-email → login → refresh → logout, and forgot/reset password, and `me`. Business rules live
in `AuthService`; views own only the HTTP/cookie mechanics. See the [API reference](#api-reference).

### `apps.buses` — routes, stops, fleet & drivers (P1)

The static transit world: `Route`, `BusStop`, `Bus`, plus driver-account management (which are
`accounts.User` rows with `role=driver`). Public read endpoints for routes & stops (including a
`?near=lat,lng` proximity filter), and admin CRUD ViewSets with extra actions (assign-driver,
maintenance, replace-stops). An idempotent `seed_demo` management command loads a Kathmandu-area
demo dataset.

---

## Data model

All domain tables inherit `TimeStampedSoftDeleteModel`. Coordinates are `DECIMAL(9,6)`; enums are
Django `TextChoices`; reference data uses `on_delete=PROTECT`; uniqueness is enforced with
**partial unique constraints** (`WHERE is_deleted = false`) so a soft-delete tombstone never blocks
reuse of a plate or a stop sequence.

### `User` (`users`)
[`apps/accounts/models.py`](apps/accounts/models.py)

| Field | Type | Notes |
|-------|------|-------|
| `email` | EmailField, unique, indexed | login identifier (no username) |
| `full_name` | CharField(150) | blank allowed |
| `phone` | CharField(20) | blank allowed |
| `role` | CharField(16), choices | `passenger` (default) / `driver` / `admin`; indexed |
| `is_verified` | bool | gates login |
| `is_active` | bool | soft-deleting a user sets this `False` (can no longer authenticate) |
| `is_staff` | bool | Django admin access |
| `created_at` / `updated_at` / `is_deleted` | — | timestamps + soft delete |

Convenience props: `is_passenger`, `is_driver`, `is_admin`. Managed by `UserManager`
(`create_user`, `create_superuser`). **Caveat:** `User.objects` does **not** filter soft-deleted
rows (it's `UserManager`, needed for `createsuperuser`) — repositories filter `is_deleted=False`
explicitly (GOTCHAS §1).

### `Route` (`routes`)
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(120) | |
| `polyline_json` | JSONField | encoded path points for the map; AI ETA refines later |
| `estimated_duration` | PositiveInteger | baseline minutes |
| `color` | CharField(7) | hex (`#1E88E5`), validated; drives the map polyline |

### `BusStop` (`bus_stops`)
| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(120) | |
| `lat` / `lng` | DecimalField(9,6) | map markers + geofencing |
| `route` | FK → Route (`PROTECT`) | `related_name="stops"` |
| `sequence` | PositiveInteger | order along the route |

Indexed on `(route, sequence)`; **partial-unique** on `(route, sequence)` for active rows.

### `Bus` (`buses`)
| Field | Type | Notes |
|-------|------|-------|
| `plate` | CharField(20) | **partial-unique** for active rows |
| `capacity` | PositiveInteger | |
| `status` | CharField(12), choices | `active` / `idle` (default) / `maintenance` / `retired`; indexed |
| `assigned_driver` | FK → User (`SET_NULL`, null) | limited to `role=driver`; bus survives driver reassignment |

> **Soft delete & uniqueness in practice:** delete a bus and its plate becomes reusable
> immediately, because the unique constraint ignores tombstones. Serializers mirror the partial
> constraint via a repository check (`plate_exists`) to return a clean `duplicate_plate` 400
> instead of a raw DB `IntegrityError` (GOTCHAS §2). Both behaviours are covered by `test_models.py`.

---

## API reference

Base URL: `/api/v1`. All responses use the [envelope](#the-response-envelope).

### Auth — `apps.accounts` (`/api/v1/auth/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register/` | AllowAny | Create a passenger (always unverified). Sends a verification email. → `201` user |
| `POST` | `/auth/verify-email/` | AllowAny | Body `{token}`. Marks the user verified |
| `POST` | `/auth/login/` | AllowAny | Body `{email, password}`. Sets `st_access` + `st_refresh` cookies; returns the user. Rejects unverified (`not_verified`) and bad creds (`invalid_credentials`) |
| `POST` | `/auth/refresh/` | AllowAny (refresh cookie) | Reads `st_refresh`, mints a fresh access (and rotated refresh), resets cookies. `401` if no/invalid cookie |
| `POST` | `/auth/logout/` | IsAuthenticated | Blacklists the refresh token and clears both cookies. → `204` |
| `POST` | `/auth/forgot-password/` | AllowAny | Body `{email}`. Always the same response (never reveals whether the account exists) |
| `POST` | `/auth/reset-password/` | AllowAny | Body `{token, new_password}` |
| `GET` | `/auth/me/` | IsAuthenticated | The current user |

### Public reads — `apps.buses` (`/api/v1/`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/routes/` | AllowAny | List/search routes. Paginated; `?search=`, `?ordering=name\|created_at\|estimated_duration` |
| `GET` | `/routes/{id}/` | AllowAny | Route detail with **ordered stops** + polyline |
| `GET` | `/stops/` | AllowAny | List stops. `?route=`, `?search=`, `?ordering=`, and `?near=lat,lng&radius=` proximity filter |
| `GET` | `/stops/{id}/` | AllowAny | Stop detail |

The `?near=` filter ([`BusStopRepository.nearby`](apps/buses/repository/BusStopRepository.py)) uses a
bounding box (no PostGIS) so it runs identically on SQLite and Postgres; default radius `1.0` km.
A malformed `near` returns `400 invalid_near`.

### Admin CRUD — `apps.buses` (`/api/v1/admin/`, `IsAdmin`)

| Method | Path | Description |
|--------|------|-------------|
| `GET/POST` | `/admin/routes/` | List / create routes |
| `GET/PUT/PATCH/DELETE` | `/admin/routes/{id}/` | Retrieve (with stops) / update / soft delete |
| `POST` | `/admin/routes/{id}/stops/` | **Replace** the route's stops with an ordered list (atomic) |
| `GET/POST` | `/admin/buses/` | List / create buses. `?status=`, `?assigned_driver=`, `?search=plate` |
| `GET/PUT/PATCH/DELETE` | `/admin/buses/{id}/` | Retrieve / update / soft delete |
| `PATCH` | `/admin/buses/{id}/assign-driver/` | Body `{driver_id}`. Rejects non-drivers (`invalid_driver`) |
| `PATCH` | `/admin/buses/{id}/maintenance/` | Flip the bus into `maintenance` (optional `{note}`) |
| `GET/POST` | `/admin/drivers/` | List / create driver accounts (created verified, no email gate) |
| `GET/PUT/PATCH/DELETE` | `/admin/drivers/{id}/` | Retrieve / update / soft delete a driver |

The driver list excludes non-drivers and soft-deleted rows. Creating a duplicate plate or driver
email returns `duplicate_plate` / `duplicate_email`.

### Schema & docs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/schema/` | OpenAPI 3 schema (JSON) |
| `GET` | `/api/docs/` | Swagger UI |
| `—` | `/admin/` | Django admin |

---

## Pagination, filtering, search & ordering

- **Pagination** — `DefaultCursorPagination` (cursor-based: stable under inserts, ideal for live
  data). Page size 20, max 100, override with `?page_size=`, ordered by `-created_at`. The
  paginated payload carries `meta.pagination = {next, prev, page_size}`. An
  `OffsetFallbackPagination` (page-number, includes `count`) is available for views that want
  jump-to-page.
- **Filtering** — `DjangoFilterBackend` via `filterset_fields` (e.g. buses `?status=`,
  `?assigned_driver=`; stops `?route=`).
- **Search** — `SearchFilter` via `search_fields` (routes/stops by `name`, buses by `plate`,
  drivers by `email`/`full_name`/`phone`). Query param `?search=`.
- **Ordering** — `OrderingFilter` via `ordering_fields`. Query param `?ordering=` (prefix `-` for
  descending).

These three backends are DRF defaults for the project (settings), so any generic view/ViewSet that
sets the corresponding `*_fields` attributes gets them for free.

---

## Error handling & domain exceptions

DRF's varied error shapes are flattened into a stable list of
`{code, field, detail}` objects by [`envelope_exception_handler`](apps/common/exceptions.py).
Nested serializer errors become dotted field paths; the machine `code` (e.g. `required`,
`invalid`, or a custom one) is preserved so the frontend can branch on it without string-matching.

Services raise **domain exceptions** — subclasses of `CustomException` (itself a DRF
`APIException`) — carrying a message, HTTP status, and a stable code:

| Exception | App | Status | Code |
|-----------|-----|--------|------|
| `InvalidCredentialsError` | accounts | 400 | `invalid_credentials` |
| `EmailNotVerifiedError` | accounts | 400 | `not_verified` |
| `DriverNotFoundError` | buses | 404 | `invalid_driver` |

Custom serializer validation codes in use: `duplicate_plate`, `duplicate_email`,
`token_expired`, `token_invalid`, `invalid_near`.

---

## Configuration & environment variables

Settings split into `base` → `{dev, prod, test}`. The active module is chosen by
`DJANGO_SETTINGS_MODULE` (defaults to `config.settings.dev` via `manage.py` / `asgi.py`;
`wsgi.py` uses `config.settings.prod`). Config is read from env vars via **django-environ**;
`base.py` calls `read_env(BASE_DIR/.env)` so a local `.env` is loaded automatically (a no-op in
containers that inject real env vars). Copy [`.env.example`](.env.example) → `.env` to start.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | which settings module |
| `DJANGO_DEBUG` | `false` | debug mode |
| `DJANGO_SECRET_KEY` | dev placeholder | **set a real secret in prod** |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | comma-separated hosts |
| `DATABASE_URL` | `postgres://postgres:postgres@localhost:5432/smart_transit` | Postgres DSN |
| `REDIS_URL` | `redis://localhost:6379/0` | cache + channel layer + Celery broker/result |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | SPA origins (credentials allowed) |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:3000` | trusted CSRF origins |
| `JWT_COOKIE_SECURE` | `false` | `true` over HTTPS (prod) |
| `FRONTEND_URL` | `http://localhost:3000` | base for verify/reset email links |

**Environment differences**

- **dev** — `DEBUG=True`; adds the DRF Browsable API renderer alongside the JSON envelope.
- **prod** — `DEBUG=False`; WhiteNoise (compressed manifest static), `SECURE_SSL_REDIRECT`,
  1-year HSTS (+subdomains/preload), nosniff, referrer policy, and `Secure` cookies. Trusts
  `X-Forwarded-Proto` from Nginx (`SECURE_PROXY_SSL_HEADER`).
- **test** — in-memory SQLite, locmem cache, in-memory channel layer, fast MD5 hashing, locmem
  email. Lets the suite run without Postgres/Redis.

Email uses the console backend in dev (links print to stdout); wire SMTP via settings in prod.

---

## Getting started

### Option A — Docker Compose (recommended)

Brings up Postgres + Redis, runs migrations once, then starts the backend processes (HTTP, WS,
Celery worker, beat). Run from the **repo root**:

```bash
docker compose up --build
```

| Service | URL / role |
|---------|-----------|
| `web` | http://localhost:8000 — DRF + Swagger at `/api/docs/`, Django admin at `/admin/` |
| `ws` | ws://localhost:9000 — Daphne ASGI (consumers land in P2) |
| `worker` / `beat` | Celery worker + scheduler |
| `postgres` / `redis` | `localhost:5432` / `localhost:6379` |

The `migrate` service is one-shot (`depends_on … service_completed_successfully`), so the app
services only start once the schema is applied. The `web` service has an HTTP healthcheck against
`/api/schema/`.

### Option B — local virtualenv

Requires a running PostgreSQL and Redis (or point `DATABASE_URL`/`REDIS_URL` at your own).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

cp .env.example .env          # adjust DATABASE_URL / REDIS_URL as needed
python manage.py migrate
python manage.py seed_demo    # optional demo data
python manage.py createsuperuser
python manage.py runserver    # http://localhost:8000
```

For the real-time process locally: `daphne -b 0.0.0.0 -p 9000 config.asgi:application`.
For background jobs: `celery -A config worker -l info` and `celery -A config beat -l info`.

---

## Database, migrations & seed data

```bash
python manage.py makemigrations     # after model changes
python manage.py migrate            # apply
python manage.py createsuperuser    # creates an admin (role=admin, verified)
python manage.py seed_demo          # idempotent demo dataset
```

Current migrations: `accounts/0001_initial`, `buses/0001_initial`.

### `seed_demo`

[`seed_demo`](apps/buses/management/commands/seed_demo.py) loads a complete demo dataset:

- **Users across every role** — 1 admin, 2 drivers, 3 passengers — all **verified** and sharing
  the password **`Demo1234!`**. The admin is also a Django superuser, so `/admin/` works out of
  the box.
- **3 Kathmandu-area routes** (Ring Road, Lagankhel–Ratnapark, Bhaktapur–Kathmandu) with ordered stops.
- **3 buses**, with the two demo drivers assigned to the first two.

| Role | Email | Password |
|------|-------|----------|
| admin | `admin.demo@smart-transit.ai` | `Demo1234!` |
| driver | `driver.demo@smart-transit.ai`, `driver.two@smart-transit.ai` | `Demo1234!` |
| passenger | `rider.demo@smart-transit.ai`, `rider.two@…`, `rider.three@…` | `Demo1234!` |

Every object is created via `get_or_create` on a natural key, and each account's password is set
explicitly with `set_password` (guarded by `check_password`), so **re-running converges to the same
state** — existing rows are left untouched.

> **Why the password is set explicitly:** a user created through `get_or_create` is built with
> `Model.create` (not `create_user`), leaving `password=""`. Django treats an empty string as a
> *usable* password (`is_password_usable("") is True`), so a `if not user.has_usable_password()`
> guard never fires and the account ends up unable to log in. The command sets the password
> directly to avoid that trap.

**Run it via Docker Compose** (from the repo root):

```bash
docker compose exec web python manage.py seed_demo      # stack already running
docker compose run --rm web python manage.py seed_demo  # stack not up — starts deps, then exits
```

Or locally: `python manage.py seed_demo`.

---

## Testing

The suite uses **pytest + pytest-django**, configured in `pyproject.toml` to run against
`config.settings.test` (in-memory SQLite, no Postgres/Redis needed).

```bash
cd backend
source .venv/bin/activate
python -m pytest                 # all 35 tests
python -m pytest apps/buses      # one app
python -m pytest -k assign_driver -v
```

**Current status: 35 passing.** Coverage by file:

| File | What it proves |
|------|----------------|
| `accounts/tests/test_auth.py` | register→verify→login flow, HttpOnly·Strict cookies, refresh rotation, unverified/bad-cred rejection, cookie auth on `/me/`, tampered-token rejection |
| `buses/tests/test_models.py` | soft delete hides from default manager, partial-unique reuse after soft delete, active-uniqueness `IntegrityError`, sequence freeing |
| `buses/tests/test_routes_api.py` | public + enveloped pagination, search filter, ordered-stops detail |
| `buses/tests/test_stops_api.py` | public listing, route filter, `?near=` geo search, malformed-`near` 400 |
| `buses/tests/test_admin_api.py` | RBAC (401/403), bus CRUD + soft delete, duplicate-plate, assign-driver (valid + non-driver), maintenance, replace-stops, driver creation/listing |

> One known benign warning: SimpleJWT emits an `InsecureKeyLengthWarning` because the test
> `SECRET_KEY` is short — irrelevant to tests, and prod uses a long secret.

---

## Code quality & conventions

- **Ruff** (lint + format), configured in `pyproject.toml`: line length 100, target `py312`,
  rule sets `E, F, I, UP, B, DJ` (pyflakes, isort, pyupgrade, bugbear, flake8-django).
  Migrations and `.venv` are excluded.

  ```bash
  ruff check .        # lint
  ruff format .       # format
  ```

- **Layered conventions** (the heart of the codebase):
  - ORM lives **only** in repositories; views/services/serializers go through them.
  - Services wrap multi-row mutations in `transaction.atomic()`.
  - Success responses use `CustomResponse`; never hand-build the envelope.
  - Domain errors raise `CustomException` subclasses (per-app `exceptions.py`) with a stable code.
  - Fix N+1 in the repository's queryset (`select_related`/`prefetch_related` + `to_attr`), then
    read the prefetched attribute in the serializer.
  - Soft delete by default; reach for `all_objects` / `hard_delete()` only deliberately.

  The full wrong-vs-right catalog lives in
  [`.claude/skills/django-expert/GOTCHAS.md`](../.claude/skills/django-expert/GOTCHAS.md); DRF API
  conventions in [`.claude/skills/drf-conventions/`](../.claude/skills/drf-conventions). There's an
  `n-plus-one-detector` skill for the queryset side.

---

## OpenAPI / Swagger

drf-spectacular generates an OpenAPI 3 schema. Views annotate request/response shapes with
`@extend_schema` and group endpoints with tags (`routes`, `stops`, `admin-routes`, `admin-buses`,
`admin-drivers`). The cookie+bearer auth is taught to the schema generator by the extension in
[`accounts/schema.py`](apps/accounts/schema.py) (registered in `AccountsConfig.ready()`), so the
schema generates cleanly without "could not resolve authenticator" warnings.

- Interactive UI: **`/api/docs/`**
- Raw schema: **`/api/schema/`** (`SCHEMA_PATH_PREFIX = /api/v1`)

---

## Processes & ports

One image, run as several processes (each compose service overrides the Dockerfile `CMD`):

| Process | Command | Port | Role |
|---------|---------|------|------|
| HTTP / DRF | `gunicorn config.wsgi` (prod) · `runserver` (dev) | 8000 | REST API, admin, Swagger |
| WebSocket / ASGI | `daphne config.asgi` | 9000 | Channels real-time (P2) |
| Celery worker | `celery -A config worker` | — | background tasks |
| Celery beat | `celery -A config beat` | — | scheduled tasks (schedule populated in P5) |

The Docker image (`python:3.13-slim`) installs `requirements/prod.txt`, copies the app, and runs as
an unprivileged `app` user. `psycopg[binary]` ships manylinux wheels, so no build toolchain or
`libpq-dev` is needed.

---

## Roadmap

This backend implements **P0 + P1** of the phased [`docs/build-plan.md`](../docs/build-plan.md).
The infrastructure for later phases already boots (empty WS router, empty Celery schedule):

| Phase | Scope | Status |
|-------|-------|--------|
| **P0** | Foundation + auth (settings, envelope, RBAC, cookie JWT, auth flows) | ✅ done |
| **P1** | Domain CRUD: routes, stops, buses, drivers + public reads | ✅ done |
| **P2** | Real-time tracking: `trips`/`gps_locations`, Channels consumers, JWT-on-connect | ⏳ scaffolded |
| **P3** | Passenger live map (frontend-led; backed by P2) | ⏳ |
| **P4** | Ticketing, wallet & payments (idempotent webhooks, `Decimal` money) | ⏳ |
| **P5** | AI modules: ETA / occupancy / route-optimize serving + Celery anomaly/maintenance | ⏳ |
| **P6** | Admin dashboard & analytics (live fleet, KPIs, rollups, exports) | ⏳ |
| **P7** | Hardening, security & deploy (Nginx, HTTPS/WSS, prod compose, observability) | ⏳ |

---

## Related documentation

| Document | What it covers |
|----------|----------------|
| [`../README.md`](../README.md) | Project overview, target stack, pinned versions |
| [`../docs/architecture.md`](../docs/architecture.md) | System topology, real-time pipeline, AI serving, security |
| [`../docs/er-diagram.md`](../docs/er-diagram.md) | All tables, relationships, enums, indexing strategy |
| [`../docs/api-contract.md`](../docs/api-contract.md) | Every `/api/v1` endpoint, the envelope, auth, pagination, WS channels |
| [`../docs/build-plan.md`](../docs/build-plan.md) | Phased delivery plan (P0 → P7) and acceptance criteria |
| [`.claude/skills/django-expert/GOTCHAS.md`](../.claude/skills/django-expert/GOTCHAS.md) | Common wrong-vs-right patterns for this codebase |
| [`.claude/skills/drf-conventions/`](../.claude/skills/drf-conventions) | DRF API conventions |
