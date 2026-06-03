---
name: drf-conventions
description: DRF API conventions for the Smart Transit AI backend. Use when asked to create, modify, or review Django REST Framework APIs, serializers, views, or endpoints.
user-invokable: true
---

# DRF Conventions — Smart Transit AI

`.claude/CLAUDE.md` and the `django-expert` skill cover architecture, boundaries, and
debugging. **This skill is the actionable recipe book**: how to add or change a DRF
endpoint in this codebase, with copy-paste-true imports and patterns.

> **Reference files — copy these, don't invent:**
> - `apps/buses/v1/views/bus_api.py`, `route_api.py`, `stop_api.py` — public reads (generics),
>   admin CRUD (`ModelViewSet` + `@action`), service-backed mutations via `CustomResponse`.
> - `apps/buses/repository/` — `BusRepository`, `RouteRepository`, `BusStopRepository`, `DriverRepository`.
> - `apps/buses/v1/services/` — `BusService`, `RouteService` (service classes with `@staticmethod`).
> - `apps/accounts/v1/views/` + `serializers/` — `APIView` flows, cookie-JWT, signed tokens.
> - `apps/common/` — `CustomResponse`, `CustomException`, `EnvelopeJSONRenderer`,
>   `envelope_exception_handler`, `BaseRepository`, pagination, permissions.

## Layout (layered — `v1/`, `repository/`, `services/` packages per app)

Call flow: **View → Service → Repository → Model**. Serializers handle I/O only.

```
apps/<app>/
  models.py
  repository/
    __init__.py                     # re-exports all repository classes
    <model>_repository.py           # ONE class per model: class XRepository(BaseRepository)
  v1/
    __init__.py
    urls.py                         # DefaultRouter for ViewSets + path() for generics; app_name set
    serializers/
      __init__.py
      <model>.py                    # read/write/action serializers; validation only
    services/
      __init__.py
      <x>_service.py                # class XService with @staticmethod methods
    views/
      __init__.py
      <x>_api.py                    # thin views: generics / ModelViewSet
  admin.py, tests/, management/commands/
```

Shared building blocks live in `apps/common/` (`CustomResponse`, `CustomException`,
`BaseRepository`, `EnvelopeJSONRenderer`, `envelope_exception_handler`, pagination, permissions,
the soft-delete base model).

## Steps to Add an Endpoint

1. **Model** (if new) in `apps/<app>/models.py` — inherit `TimeStampedSoftDeleteModel`,
   set `db_table`, use `TextChoices`, partial unique constraints (`condition=Q(is_deleted=False)`).
2. **Repository** in `apps/<app>/repository/<model>_repository.py` — subclass `BaseRepository`,
   set `model = X`, add `@classmethod` query methods with `select_related`/`prefetch_related`.
   ALL ORM lives here; no direct `Model.objects` access outside a repository.
3. **Service** in `apps/<app>/v1/services/<x>_service.py` — a class with `@staticmethod` methods.
   Business rules, state checks, `with transaction.atomic():`, raise `CustomException`. Call
   repositories. No direct ORM, no DRF imports.
4. **Serializer(s)** in `apps/<app>/v1/serializers/<model>.py` — validation + representation only
   (no `create`/`update` model methods; views drive services). Uniqueness checks call the repository.
5. **View** in `apps/<app>/v1/views/<x>_api.py` — pick a generic or `ModelViewSet` (below);
   set `permission_classes` and `@extend_schema`. `get_queryset()` calls the repository.
   Mutations: validate → service → `CustomResponse`.
6. **URL** in `apps/<app>/v1/urls.py` — `DefaultRouter` for ViewSets, `path()` for generics.
7. **Mount** in `config/urls.py` → `api_v1_patterns` (once per app, under `/api/v1/`).

## Import Paths

```python
# Views
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework import status

# Success responses — use CustomResponse (not bare Response) in mutating views
from apps.common.response import CustomResponse          # builds {data, meta, errors}, tagged __enveloped__

# Domain exceptions — raised by services, converted to {errors:[...]} by the handler
from apps.common.exceptions import CustomException      # APIException subclass; CustomException(message=, status=, code=)

# Repository base class (subclass in each app's repository/)
from apps.common.repository import BaseRepository

# Per-app repository imports (example: buses)
from apps.buses.repository import BusRepository, RouteRepository, BusStopRepository, DriverRepository

# Permissions (default is IsAuthenticated; opt into these per view)
from apps.common.permissions import IsAdmin, IsDriver, IsPassenger, IsOwnerOrAdmin
from rest_framework.permissions import AllowAny, IsAuthenticated

# Serializers / validation — plain DRF, raise with a stable code=
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, NotAuthenticated, PermissionDenied, NotFound

# Pagination (default is cursor; offset variant for jump-to-page tables)
from apps.common.pagination import DefaultCursorPagination, OffsetFallbackPagination

# OpenAPI
from drf_spectacular.utils import extend_schema, extend_schema_view

# Filtering backends are wired globally in settings — views just set the *_fields attrs.
```

> There is **no** `BaseARView` / `CamelCaseSerializer` / `required_resources` /
> resource-PK permissions / tenant headers / `django_tenants` in this project. If you
> see those in ported code, they belong to a different codebase — use the imports above.

## Response & Errors — the envelope

Every response is wrapped to `{data, meta, errors}`. Mutating views use `CustomResponse`
(from `apps/common/response.py`) which tags the payload `__enveloped__` so
`EnvelopeJSONRenderer` passes it through untouched. Public reads that return bare
`Response` are also wrapped by the renderer. Both paths produce the same wire shape.

```python
# Success in a mutating view — use CustomResponse
from apps.common.response import CustomResponse

return CustomResponse(BusSerializer(bus).data, status=status.HTTP_201_CREATED)
return CustomResponse(BusSerializer(bus).data, message="Driver assigned.")
return CustomResponse(BusSerializer(bus).data)   # 200 by default

# Error from a service — raise CustomException (no try/except in views)
from apps.common.exceptions import CustomException

raise CustomException(message="No active driver with this id.", status=404, code="invalid_driver")

# Error from a serializer — raise ValidationError with a stable code=
raise serializers.ValidationError("A bus with this plate already exists.", code="duplicate_plate")
```

`envelope_exception_handler` (the DRF `EXCEPTION_HANDLER`) converts both exception types
into `{data: null, meta: null, errors: [{code, field, detail}]}`.

Rules:
- **Never** build the `{data, meta, errors}` dict by hand and **never** `try/except` to format
  errors in a view — raise and let the handler do it.
- **Always** attach a stable machine `code=` (`duplicate_plate`, `token_expired`,
  `invalid_driver`, …) so the frontend can branch on it.
- Lists routed through a pagination class are auto-wrapped to `{data: [...], meta: {pagination}}`.

## View Patterns

### Public read (generics — `get_queryset()` from repository)

```python
# apps/buses/v1/views/route_api.py
@extend_schema(tags=["routes"])
class RouteListView(ListAPIView):
    """`GET /routes/` — list/search routes (public)."""

    serializer_class = RouteListSerializer
    permission_classes = [AllowAny]          # global default is IsAuthenticated — override for public
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "estimated_duration"]

    def get_queryset(self):
        return RouteRepository.list_queryset()   # repository owns the ORM, not the view


@extend_schema(tags=["routes"])
class RouteDetailView(RetrieveAPIView):
    """`GET /routes/{id}/` — route detail with ordered stops + polyline (public)."""

    serializer_class = RouteDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return RouteRepository.detail_queryset()  # prefetches ordered_stops via Prefetch(to_attr=)
```

### Admin CRUD (ModelViewSet — validate → service → CustomResponse)

```python
# apps/buses/v1/views/bus_api.py
@extend_schema_view(
    list=extend_schema(tags=["admin-buses"]),
    retrieve=extend_schema(tags=["admin-buses"]),
    create=extend_schema(tags=["admin-buses"]),
    update=extend_schema(tags=["admin-buses"]),
    partial_update=extend_schema(tags=["admin-buses"]),
    destroy=extend_schema(tags=["admin-buses"]),
)
class AdminBusViewSet(ModelViewSet):
    permission_classes = [IsAdmin]
    filterset_fields = ["status", "assigned_driver"]
    search_fields = ["plate"]
    ordering_fields = ["plate", "status", "created_at"]

    def get_queryset(self):
        return BusRepository.active()   # select_related("assigned_driver") inside the repository

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return BusWriteSerializer
        return BusSerializer

    def create(self, request, *args, **kwargs):
        write = BusWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        bus = BusService.create(write.validated_data)          # service wraps transaction.atomic()
        return CustomResponse(BusSerializer(bus).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = BusWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        bus = BusService.update(instance, write.validated_data)
        return CustomResponse(BusSerializer(bus).data)

    @action(detail=True, methods=["patch"], url_path="assign-driver")
    def assign_driver(self, request, pk=None):
        bus = self.get_object()
        serializer = AssignDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bus = BusService.assign_driver(bus, serializer.validated_data["driver_id"])
        return CustomResponse(BusSerializer(bus).data)
```

### Custom flow (APIView)

Use `APIView` when there's no model-CRUD mapping (auth, token flows). Validate with a
serializer, call a service, return `CustomResponse`. See `apps/accounts/v1/views/`.

**Keep views thin:** validation in serializers, multi-step mutations in service classes, no manual
envelope construction. Declare `permission_classes` on **every** view.

## Repository Conventions

- **One class per model**, subclasses `BaseRepository` from `apps/common/repository/base.py`.
- Set `model = X` on the class. All query methods are `@classmethod`.
- `BaseRepository` provides: `active()` (excludes soft-deleted), `get_or_none(**filters)`,
  `apply_update(instance, data)` (PATCH idiom with `update_fields`).
- Override `active()` to add default `select_related` (e.g. `BusRepository.active()` adds
  `select_related("assigned_driver")` to avoid N+1 on `assigned_driver.email`).
- Name query methods descriptively: `list_queryset()`, `detail_queryset()`, `get_by_id()`,
  `plate_exists()`, `nearby()`. Services and views call these; no raw `Model.objects` elsewhere.

```python
# apps/buses/repository/bus_repository.py
class BusRepository(BaseRepository):
    model = Bus

    @classmethod
    def active(cls):
        return Bus.objects.select_related("assigned_driver")

    @classmethod
    def plate_exists(cls, plate: str, *, exclude_pk=None) -> bool:
        qs = Bus.objects.filter(plate=plate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()
```

## Service Conventions

- **Classes with `@staticmethod` methods**, one file per domain (e.g. `BusService`, `RouteService`).
- Business rules and state checks live here. Raise `CustomException` (not DRF exceptions) when a
  rule is violated.
- Every mutation is wrapped in `with transaction.atomic():`.
- No direct ORM access — call repository methods. No DRF imports.

```python
# apps/buses/v1/services/bus_service.py
class BusService:
    @staticmethod
    def assign_driver(bus: Bus, driver_id: int) -> Bus:
        driver = DriverRepository.get_driver(driver_id)
        if driver is None:
            raise CustomException(
                message="No active driver with this id.", status=404, code="invalid_driver"
            )
        with transaction.atomic():
            bus.assigned_driver = driver
            bus.save(update_fields=["assigned_driver", "updated_at"])
        return bus
```

## Serializer Conventions

- **Split read and write.** Read serializers set `read_only_fields = fields`. Write serializers
  expose only the writable fields. Serializers do NOT call `create()`/`update()` on models — views
  pass `validated_data` to a service method instead.
- **Stable `code=`** on every `ValidationError`.
- **Mirror partial-unique constraints.** A `UniqueConstraint(condition=Q(is_deleted=False))` only
  covers active rows, so declare the field plainly (to suppress DRF's auto `UniqueValidator`) and
  check uniqueness via the **repository** in `validate_<field>`:

```python
# apps/buses/v1/serializers/bus.py
class BusWriteSerializer(serializers.ModelSerializer):
    plate = serializers.CharField(max_length=20)   # plain → no surprise auto-validator

    class Meta:
        model = Bus
        fields = ("plate", "capacity", "status", "assigned_driver")

    def validate_plate(self, value: str) -> str:
        exclude_pk = self.instance.pk if self.instance is not None else None
        if BusRepository.plate_exists(value, exclude_pk=exclude_pk):   # repository, not raw ORM
            raise serializers.ValidationError(
                "A bus with this plate already exists.", code="duplicate_plate"
            )
        return value
```

- **Action payloads** are plain `serializers.Serializer` subclasses (e.g. `AssignDriverSerializer`,
  `AssignStopsSerializer`) — validate the input, let the view hand `validated_data` to a service.
- **Nested writes** that replace a set go through a service (`RouteService.replace_stops`), not
  the serializer.
- API is **snake_case** end to end — there is no camelCase conversion layer.

## SerializerMethodField — N+1 Rules

`SerializerMethodField` runs once **per instance**. Any DB access inside `get_<field>` is a
guaranteed N+1 on list endpoints (fine on a single-object detail view, deadly on a list).

**NEVER do this on a list endpoint:**

```python
# ❌ one query per row
class RouteListSerializer(serializers.ModelSerializer):
    stop_count = serializers.SerializerMethodField()
    first_stop = serializers.SerializerMethodField()

    def get_stop_count(self, obj):
        return obj.stops.count()                              # COUNT(*) per route
    def get_first_stop(self, obj):
        return obj.stops.order_by("sequence").first().name    # SELECT per route
```

**Fix order — try in this sequence:**

### 1. Annotate in the queryset (preferred for counts / booleans / aggregates)

Annotations belong in a **repository** method. The view calls that method from `get_queryset()`.

```python
# apps/buses/repository/route_repository.py
@classmethod
def annotated_list(cls):
    from django.db.models import Count, Exists, OuterRef
    return Route.objects.annotate(
        stop_count=Count("stops"),
        has_stops=Exists(BusStop.objects.filter(route=OuterRef("pk"))),
    )

# serializer — plain fields, no method
class RouteListSerializer(serializers.ModelSerializer):
    stop_count = serializers.IntegerField(read_only=True)
    has_stops = serializers.BooleanField(read_only=True)
```

Use `Count`, `Sum`, `Avg`, `Max`, `Min`, `Exists`, `Subquery`, `Case/When` — anything ORM-expressible.

### 2. Prefetch when you need whole related rows

Prefetch setup belongs in the **repository**. `RouteRepository.detail_queryset()` is the live
example: it uses `Prefetch("stops", queryset=BusStop.objects.order_by("sequence"), to_attr="ordered_stops")`.
The `RouteDetailSerializer` reads the cached attribute — zero DB hits in the serializer.

```python
# apps/buses/repository/route_repository.py — already done
@classmethod
def detail_queryset(cls):
    return Route.objects.prefetch_related(
        Prefetch(
            "stops",
            queryset=BusStop.objects.order_by("sequence"),
            to_attr="ordered_stops",   # attached as a plain list, not a queryset
        )
    )

# apps/buses/v1/serializers/route.py — reads the prefetched attr
class RouteDetailSerializer(serializers.ModelSerializer):
    stops = serializers.SerializerMethodField()

    def get_stops(self, obj: Route) -> list[dict]:
        stops = getattr(obj, "ordered_stops", [])   # already in memory — no ORM
        return BusStopSerializer(stops, many=True).data
```

Slice/iterate prefetched results **in Python** (`obj.ordered_stops[:5]`). Calling `.filter()` or
`.order_by()` on the prefetched manager **breaks the cache** and re-queries.

For forward FKs use `select_related` in the repository (e.g. `BusRepository.active()` calls
`Bus.objects.select_related("assigned_driver")` so `assigned_driver.email` is free in the serializer).

### 3. Compute in a service before serialization

For cross-row state or logic that's awkward in SQL, compute once in the service class, attach to
each instance (or pass a dict via serializer `context`), and read it in the serializer as a plain
field.

### Allowed reads inside `get_<field>`

- Plain attribute access (`obj.field`, `obj.fk.field`) where the FK is `select_related`'d.
- Iterating an **already-prefetched** relation (e.g. `obj.ordered_stops`).
- Pure-Python computation on the instance (no ORM).

If you're writing `obj.<related>.count()/.filter()/.first()` or `Model.objects.filter(...)` inside a
serializer method, stop and pick fix #1, #2, or #3.

## Pagination

- **Default: `DefaultCursorPagination`** (cursor; stable under inserts; `page_size` 20, max 100,
  `?page_size=`, ordered `-created_at`). Applied globally via `REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]`.
- **`OffsetFallbackPagination`** for admin tables that need jump-to-page (page numbers + count).
  Set `pagination_class = OffsetFallbackPagination` on that view.
- Both tag their payload `__paginated__` so `EnvelopeJSONRenderer` lifts `results`/`pagination`
  into `data`/`meta` — you never assemble that yourself.

## Filtering

Backends are wired globally (`DjangoFilterBackend` + `SearchFilter` + `OrderingFilter`). A view just
declares the field lists — no FilterSet classes or separate `filters/` modules in this project:

```python
class AdminBusViewSet(ModelViewSet):
    filterset_fields = ["status", "assigned_driver"]   # exact-match query params
    search_fields = ["plate"]                          # ?search=
    ordering_fields = ["plate", "status", "created_at"]  # ?ordering=
```

For a structured/custom query param, override `get_queryset()` and raise a clean `ValidationError`
with a `code=` on bad input (see `StopListView` in `apps/buses/v1/views/stop_api.py` parsing
`?near=lat,lng&radius=`). A `django_filters` `FilterSet` is available if a view ever needs
range/relational filters — add it then, scoped to that view.

## OpenAPI / Swagger

- Decorate views with `@extend_schema(...)`; for ViewSets use `@extend_schema_view(list=…, create=…)`
  with per-action `tags`. Pass `request=`/`responses=` serializers so `/api/docs/` is accurate.
- Schema lives at `/api/schema/`, Swagger UI at `/api/docs/`. Settings in `SPECTACULAR_SETTINGS`
  (`COMPONENT_SPLIT_REQUEST=True`, `SCHEMA_PATH_PREFIX="/api/v1"`).
- The cookie-JWT security scheme is registered in `apps/accounts/schema.py` and loaded via
  `AccountsConfig.ready()` — keep `/api/schema/ --fail-on-warn` clean.

## URL Wiring

```
config/urls.py
  /admin/                         → Django admin
  /api/v1/                        → api_v1_patterns:
      auth/   → apps.accounts.v1.urls    (APIViews via path())
      ""      → apps.buses.v1.urls       (DefaultRouter for ViewSets + path() for generics)
  /api/schema/  /api/docs/        → drf-spectacular
```

In an app's `v1/urls.py`: set `app_name`, register ViewSets on a `DefaultRouter`
(`router.register("admin/buses", AdminBusViewSet, basename="admin-bus")`), add `path()` entries for
generics, and end with `*router.urls`. Example from `apps/buses/v1/urls.py`:

```python
app_name = "buses"

router = DefaultRouter()
router.register("admin/routes", AdminRouteViewSet, basename="admin-route")
router.register("admin/buses", AdminBusViewSet, basename="admin-bus")
router.register("admin/drivers", AdminDriverViewSet, basename="admin-driver")

urlpatterns = [
    path("routes/", RouteListView.as_view(), name="route-list"),
    path("routes/<int:pk>/", RouteDetailView.as_view(), name="route-detail"),
    path("stops/", StopListView.as_view(), name="stop-list"),
    path("stops/<int:pk>/", StopDetailView.as_view(), name="stop-detail"),
    *router.urls,
]
```

## Permissions / Auth (quick reference)

- Global default is `IsAuthenticated`. Override per view: `[AllowAny]` (public reads), `[IsAdmin]`,
  `[IsDriver]`, `[IsPassenger]`, or `[IsOwnerOrAdmin]` (set `owner_field` on the view).
- Auth is cookie-JWT (`CookieJWTAuthentication`, `st_access`/`st_refresh`) **or** a Bearer header.
  Tokens are issued/cleared only in `apps/accounts/v1/views/`; never put a JWT in a response body.
- Per-role rate limits exist in settings (`passenger`/`driver`/`admin`) but are **inert** until a
  view sets `throttle_scope = "<role>"` (only `anon` 30/min is live globally).

## After Writing Code

From `backend/` using the project venv; fix anything that fails before presenting (no pre-commit
or Makefile in this repo):

```bash
.venv/bin/ruff check . && .venv/bin/ruff format .
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run   # did a model change need a migration?
.venv/bin/python -m pytest -q                                  # settings from pyproject (config.settings.test)
.venv/bin/python manage.py spectacular --validate --fail-on-warn
```

Tests use pytest + `APIClient`: `@pytest.mark.django_db`, role fixtures via
`User.objects.create_user(..., role=User.Roles.ADMIN)`, `client.force_authenticate(user=...)`, and
assertions on the **rendered envelope** — `resp.json()["data"]` / `["errors"]`, not `resp.data`.
See `apps/buses/tests/` and `apps/accounts/tests/test_auth.py`.

For deeper architecture, debugging, soft-delete/Celery questions, see the **`django-expert`** skill.
