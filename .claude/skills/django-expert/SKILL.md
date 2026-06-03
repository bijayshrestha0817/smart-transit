---
name: django-expert
description: Expert Django engineer agent for the Smart Transit AI backend. Use for architecture decisions, debugging, performance optimization, the layered View→Service→Repository flow, the response envelope, RBAC/auth (cookie-JWT), soft delete, Celery/Channels groundwork, migration safety, and any Django question specific to this codebase.
user-invokable: true
---

# Expert Django Engineer — Smart Transit AI

You are an expert Django engineer with deep knowledge of **this** codebase: a single-tenant
Django 6.0 / DRF 3.17 backend under `backend/`, organized in a **layered architecture with
v1 versioning**. `.claude/CLAUDE.md` and `dev/memory/zero/CONTEXT.md` cover the rules and the
project map — this skill gives you the **decision frameworks, patterns, and gotchas**.

> **Canonical references — read these first when in doubt (PascalCase files, `service/` singular):**
> - `apps/buses/repository/BusRepository.py` + `RouteRepository.py` — class-per-model data access.
> - `apps/buses/v1/service/BusService.py` + `RouteService.py` — service classes (rules + transactions).
> - `apps/buses/v1/views/BusViews.py` (admin ViewSet) + `RouteViews.py` (public generics + admin) — thin views.
> - `apps/accounts/v1/service/AuthService.py` + `views/AuthViews.py` — auth flows, cookie-JWT.
> - `apps/buses/enums.py` + `exceptions.py` — `TextChoices` enums (`BusStatus`, aliased `Bus.Status`) and
>   domain exceptions (`DriverNotFoundError`); accounts mirrors this (`UserRole`, `InvalidCredentialsError`).
> - `apps/common/` — `response.py` (CustomResponse), `exceptions.py` (CustomException + handler),
>   `repository/base.py` (BaseRepository), pagination, permissions, soft-delete model.

## Architecture: View → Service → Repository → Model

```
apps/<app>/
  models.py                         # tables (inherit TimeStampedSoftDeleteModel)
  enums.py                          # TextChoices enums, aliased on the model (Bus.Status = BusStatus)
  exceptions.py                     # domain CustomException subclasses (DriverNotFoundError, …)
  urls.py                           # version dispatch: path("v1/", include("apps.<app>.v1.urls"))
  repository/<Model>Repository.py   # class per model — ALL ORM lives here (PascalCase file)
  v1/
    serializers/<Model>Serializer.py  # validation + representation only
    service/<Domain>Service.py        # business rules, transactions, domain exceptions (service/ singular)
    views/<Domain>Views.py            # thin: validate → service → CustomResponse
    urls.py
config/urls.py  →  /api/  includes apps.<app>.urls  →  v1/  includes apps.<app>.v1.urls
```

| It IS | It is NOT |
|-------|-----------|
| **Layered**: View → Service → Repository → Model, in **v1 packages** | flat — `apps/<app>/{views,services,serializers}.py` are gone |
| `{data, meta, errors}` via **`CustomResponse`** (success) + **`CustomException`** + handler (errors) | hand-built envelopes; `CustomResponse`/`CustomException` **do exist** (`apps/common/`) |
| **Repository = class per model** (`<Model>Repository.py`), owns ALL ORM | ORM inside views, services, or serializer methods |
| **Services = `@staticmethod` classes** in `v1/service/` (singular): rules, `transaction.atomic`, raise a domain exception | business logic in views or module-level functions |
| **Single-tenant** Postgres + Redis | multi-tenant — no `django_tenants` / `tenant_context` / `TENANT_APPS` |
| Soft delete via `TimeStampedSoftDeleteModel` | `simple_history`; no `created_by`/`updated_by` |
| Celery + Channels **configured** | used yet — no `tasks.py` / consumers (P2/P5 work) |

## Decision Frameworks

### "Where does this code go?"

```
HTTP routing, status, which serializer/permission   → View (thin) — apps/<app>/v1/views/<Domain>Views.py
Input validation, field rules, uniqueness mirror     → Serializer (raise ValidationError code=)
Business rule, state check, multi-step mutation, txn  → Service class (raise a domain CustomException)
ANY ORM — query, create, update, soft-delete          → Repository class (<Model>Repository.py, per model)
Schema, constraints, choices, soft-delete behavior     → Model (inherit TimeStampedSoftDeleteModel)
Choice enum (TextChoices)                              → apps/<app>/enums.py (aliased on the model)
Reusable domain error                                  → apps/<app>/exceptions.py (CustomException subclass)
Async / background job                                  → Celery task apps/<app>/tasks.py (none yet)
Reused across apps (response, pagination, permissions)  → apps/common/
```

**When in doubt:** mirror `apps/buses` (View → Service → Repository → Model).

### "select_related or prefetch_related?" — and it goes in the **repository**

```
ForeignKey / OneToOne (forward)     → select_related("field")   e.g. BusRepository.active() = Bus.objects.select_related("assigned_driver")
Reverse FK / ManyToMany             → prefetch_related("related_name")   e.g. Route → "stops"
Reverse FK needing filter/order     → Prefetch("stops", queryset=BusStop.objects.order_by("sequence"), to_attr="ordered_stops")
Nested FK depth                     → select_related("fk__nested_fk")
A single derived value from a child → annotate(... Count/Exists/Subquery ...)
```

Optimizations live in the repository's queryset methods (e.g. `RouteRepository.detail_queryset()`);
the serializer reads the prefetched attribute (`getattr(obj, "ordered_stops", [])`) — never queries.

### "How do I signal this error?"

```
Input/field validation failure   → serializer raises serializers.ValidationError("msg", code="stable_code")
Business-rule violation           → service raises a domain exception (CustomException subclass in apps/<app>/exceptions.py)
Entity not found                  → repository returns None → service raises e.g. DriverNotFoundError() (404)
Not authenticated / perm denied   → NotAuthenticated / permission class returns False (auto 401/403)
Unexpected server error           → let it bubble — handler returns None, Django emits a clean 500
```

`apps/common/exceptions.py::envelope_exception_handler` converts **both** `CustomException` (and its
subclasses) and DRF errors into the `{data, meta, errors}` error list `[{code, field, detail}]`. Never
catch-and-format in a view; never assemble the envelope by hand.

## Patterns You Must Follow

### Repository (class per model — all ORM)

```python
from apps.buses.models import Bus
from apps.common.repository import BaseRepository


class BusRepository(BaseRepository):
    model = Bus

    @classmethod
    def active(cls):
        return Bus.objects.select_related("assigned_driver")  # default shaping for serializers

    @classmethod
    def get_by_id(cls, bus_id):
        return cls.active().filter(id=bus_id).first()

    @classmethod
    def plate_exists(cls, plate, *, exclude_pk=None):
        qs = Bus.objects.filter(plate=plate)
        return qs.exclude(pk=exclude_pk).exists() if exclude_pk else qs.exists()
```

`BaseRepository` (`apps/common/repository/base.py`) gives `active()`, `get_or_none()`, `apply_update()`.
Rules: **one class per model**, `@classmethod`, **all ORM here**, no business rules, no DRF. File is
`repository/<Model>Repository.py`; re-export it from `repository/__init__.py`.

### Service (class — rules, transactions, domain exceptions)

```python
# apps/buses/v1/service/BusService.py
from django.db import transaction

from apps.buses.exceptions import DriverNotFoundError
from apps.buses.repository import BusRepository, DriverRepository


class BusService:
    @staticmethod
    def assign_driver(bus, driver_id):
        driver = DriverRepository.get_driver(driver_id)
        if driver is None:
            raise DriverNotFoundError()        # CustomException subclass → 404, code "invalid_driver"
        with transaction.atomic():
            bus.assigned_driver = driver
            bus.save(update_fields=["assigned_driver", "updated_at"])
        return bus
```

Rules: **`@staticmethod` class** in `v1/service/` (singular), `with transaction.atomic():` around
multi-step mutations, raise a **domain exception** from `apps/<app>/exceptions.py` (a `CustomException`
subclass) for rule/state failures, **call repositories** (no direct ORM), **no DRF imports**.

### Thin View

```python
# Admin CRUD — ModelViewSet delegating to the service, returning CustomResponse
class AdminBusViewSet(ModelViewSet):
    permission_classes = [IsAdmin]
    def get_queryset(self):
        return BusRepository.active()
    def get_serializer_class(self):
        return BusWriteSerializer if self.action in ("create", "update", "partial_update") else BusSerializer
    def create(self, request, *args, **kwargs):
        write = BusWriteSerializer(data=request.data); write.is_valid(raise_exception=True)
        bus = BusService.create(write.validated_data)
        return CustomResponse(BusSerializer(bus).data, status=status.HTTP_201_CREATED)

# Public reads — generics with the base queryset from the repository (auto pagination + OpenAPI)
class RouteListView(ListAPIView):
    serializer_class = RouteListSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        return RouteRepository.list_queryset()
```

Rules: **thin** — validate via serializer → call service → return `CustomResponse`; `get_queryset()`
sources from the repository; declare `permission_classes` explicitly; decorate with `@extend_schema`.
View files are named per domain (`BusViews.py`, `RouteViews.py`, `StopViews.py`, `DriverViews.py`).

### Serializer (validation + representation only)

```python
class BusWriteSerializer(serializers.ModelSerializer):
    plate = serializers.CharField(max_length=20)  # plain → no auto UniqueValidator

    class Meta:
        model = Bus
        fields = ("plate", "capacity", "status", "assigned_driver")

    def validate_plate(self, value):
        exclude_pk = self.instance.pk if self.instance is not None else None
        if BusRepository.plate_exists(value, exclude_pk=exclude_pk):   # uniqueness check via the repository
            raise serializers.ValidationError("A bus with this plate already exists.", code="duplicate_plate")
        return value
```

Rules: **no `create`/`update` model methods** (views drive services); uniqueness mirror calls the
repository; every `ValidationError` carries a stable `code=`. Split read vs write serializers. File is
`v1/serializers/<Model>Serializer.py`.

### CustomResponse / CustomException

```python
from apps.common.response import CustomResponse        # success → {data, meta, errors}
from apps.common.exceptions import CustomException      # base domain error
from apps.buses.exceptions import DriverNotFoundError   # per-app subclass (preferred for recurring errors)

return CustomResponse(BusSerializer(bus).data, status=status.HTTP_201_CREATED)
raise DriverNotFoundError()                                            # → 404, code "invalid_driver"
raise CustomException(message="…", status=409, code="conflict")        # one-off, no dedicated subclass
```

`CustomResponse` builds `{data, meta, errors}` (tagged `__enveloped__` so the renderer passes it
through — the wire shape is identical to before). List/detail via DRF generics use the cursor
paginator/renderer. `CustomException` is an `APIException` subclass; per-app subclasses bake in the
`message`/`status`/`code`. The handler flattens all of them.

### Model

```python
# apps/buses/enums.py
class BusStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    IDLE = "idle", "Idle"
    MAINTENANCE = "maintenance", "Maintenance"
    RETIRED = "retired", "Retired"

# apps/buses/models.py
from .enums import BusStatus

class Bus(TimeStampedSoftDeleteModel):
    Status = BusStatus  # enum lives in enums.py; aliased so Bus.Status.X keeps working
    plate = models.CharField(max_length=20)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IDLE)
    assigned_driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_buses", limit_choices_to={"role": "driver"})

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "buses"
        constraints = [models.UniqueConstraint(fields=["plate"], condition=Q(is_deleted=False),
            name="uniq_bus_plate_active")]
```

Rules: **inherit `TimeStampedSoftDeleteModel`** (created_at/updated_at/is_deleted + soft-delete +
`all_objects` escape hatch), set `db_table`, define `TextChoices` enums in `apps/<app>/enums.py` and
**alias them on the model** (`Status = BusStatus`) so existing `Bus.Status.X` references and migrations
are unaffected, `DECIMAL(9,6)` coords, `on_delete=PROTECT` for reference data / `SET_NULL` for soft
links, **partial unique constraints** (`condition=Q(is_deleted=False)`). No `created_by`/`updated_by`.

### Auth & Permissions

- JWTs are delivered **only** as HttpOnly cookies (`st_access`/`st_refresh`); `CookieJWTAuthentication`
  reads the cookie or a `Bearer` header. Cookie mechanics live in `apps/accounts/v1/views/AuthViews.py`;
  business logic (credential + verified checks via `InvalidCredentialsError`/`EmailNotVerifiedError`,
  reset) in `AuthService` (`apps/accounts/v1/service/AuthService.py`). Email-verify / password-reset use
  Django signed tokens (`apps/accounts/tokens.py`). SimpleJWT: 15 m / 7 d, rotation + blacklist.
- RBAC via `apps/common/permissions.py` (`IsAdmin`/`IsDriver`/`IsPassenger`/`IsOwnerOrAdmin`) + `User.role`
  (`passenger`/`driver`/`admin`; the `UserRole` enum is in `apps/accounts/enums.py`, aliased `User.Roles`).
  Default is `IsAuthenticated`; public reads override with `AllowAny`. Drivers are `User` rows with
  `role=driver` — no separate Driver model.

### Pagination / Filtering / Celery

- Default `DefaultCursorPagination` (cursor, page_size 20, max 100); `OffsetFallbackPagination` for
  jump-to-page. Filtering is global — views set `filterset_fields`/`search_fields`/`ordering_fields`.
- **Celery is configured but unused** (no `tasks.py` yet). When you add the first task: single-tenant,
  `@shared_task(bind=True, max_retries=3)`, query models directly (no `tenant_context`), exponential
  backoff on retry.

## Import Quick Reference

> DRF API recipes live in the `drf-conventions` skill; N+1 analysis in `n-plus-one-detector`.

```python
# Response / errors
from apps.common.response import CustomResponse
from apps.common.exceptions import CustomException          # base; prefer a per-app subclass for recurring errors
from rest_framework import serializers                      # serializers.ValidationError("msg", code="...")

# Repository / service base
from apps.common.repository import BaseRepository

# Views / permissions / schema
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.viewsets import ModelViewSet
from apps.common.permissions import IsAdmin, IsDriver, IsPassenger, IsOwnerOrAdmin
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view

# Models / transactions / user / celery
from apps.common.models import TimeStampedSoftDeleteModel
from django.db import transaction
from django.contrib.auth import get_user_model       # User = get_user_model()
from celery import shared_task                        # no tasks exist yet
```

## Debugging Checklist

1. **401 when expecting 200?** `CookieJWTAuthentication` needs the `st_access` cookie (or Bearer);
   browser calls need `CORS_ALLOW_CREDENTIALS=True` + the `SameSite=Strict` cookie to be sent.
2. **403?** The view's `permission_classes` doesn't match `request.user.role` (default `IsAuthenticated`).
3. **Soft-deleted rows showing up?** `User.objects` (UserManager) does **not** hide soft-deleted rows —
   the account repositories filter `is_deleted=False`. Domain models: `objects` hides them, `all_objects` doesn't.
4. **`IntegrityError` on create?** Partial unique only covers active rows — mirror the check in the
   serializer via the repository (`*Repository.*_exists`).
5. **Test reads `None` / wrong shape?** Assert on `resp.json()["data"]`/`["errors"]`, not `resp.data`.
6. **Endpoint slow / N+1?** Add `select_related`/`prefetch_related`/`annotate` in the **repository**
   queryset method; the serializer should read prefetched attrs, not query. (See `n-plus-one-detector`.)
7. **Multi-step mutation half-applied?** Wrap it in `with transaction.atomic():` in the service.
8. **Per-role rate limit not enforced?** Scoped rates are defined in settings but **inert** until a
   view sets `throttle_scope = "<role>"`; only `AnonRateThrottle` (30/min) is live.
9. **Schema warning / endpoint missing from `/api/docs/`?** Add `@extend_schema`; the cookie-JWT scheme
   is registered in `apps/accounts/schema.py` via `AccountsConfig.ready()`.
10. **New endpoint 404s?** Check all three URL layers: `v1/urls.py` (route), `apps/<app>/urls.py`
    (version dispatch, `path("v1/", …)`), and `config/urls.py` (mounts the app at `/api/`).

## After Writing Code

From `backend/` using the project venv; fix anything that fails before presenting (no pre-commit / Makefile):

```bash
.venv/bin/ruff check . && .venv/bin/ruff format .
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python -m pytest -q                       # settings from pyproject (config.settings.test)
.venv/bin/python manage.py spectacular --validate --fail-on-warn
```

Tests use pytest + `APIClient`: `@pytest.mark.django_db`, role fixtures, `client.force_authenticate(user=...)`,
and assertions on the rendered envelope (`resp.json()["data"]` / `["errors"]`). See `apps/buses/tests/`
and `apps/accounts/tests/test_auth.py`.

## Common Gotchas

See [GOTCHAS.md](GOTCHAS.md) — all grounded in this codebase: `User.objects` doesn't hide soft-deleted
rows; partial-unique serializer mirror (via repository); never hand-build the envelope (use `CustomResponse`
/ raise a domain `CustomException`); missing `transaction.atomic()` in services; N+1 fixed in the repository;
throttle scopes defined-but-inert; assert `resp.json()` not `resp.data`.
