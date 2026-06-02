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
> - `apps/buses/views.py` + `serializers.py` + `services.py` — public reads (generics),
>   admin CRUD (`ModelViewSet` + `@action`), service-backed mutations.
> - `apps/accounts/views.py` + `serializers.py` — `APIView` flows, cookie-JWT, signed tokens.
> - `apps/common/` — the renderer, exception handler, pagination, permissions you build on.

## Layout (flat — there is no `v1/` / `repository/` / `service/` tree)

One module per concern, per app:

```
apps/<app>/
  models.py        # tables (inherit TimeStampedSoftDeleteModel)
  serializers.py   # validation + read/write representations
  services.py      # OPTIONAL — module-level functions for multi-step mutations
  views.py         # thin views: APIView / generics / ModelViewSet
  urls.py          # app router + paths; app_name set
  admin.py, tests/, management/commands/
```

Shared building blocks live in `apps/common/` (renderer, exceptions, pagination,
permissions, the soft-delete base model).

## Steps to Add an Endpoint

1. **Model** (if new) in `apps/<app>/models.py` — inherit `TimeStampedSoftDeleteModel`,
   set `db_table`, use `TextChoices`, partial unique constraints (`condition=Q(is_deleted=False)`).
2. **Serializer(s)** in `apps/<app>/serializers.py` — split read vs write; `code=` on every error.
3. **Service** (only if the mutation touches >1 row/model) — a plain function in
   `apps/<app>/services.py` wrapped in `with transaction.atomic():`.
4. **View** in `apps/<app>/views.py` — pick `APIView` / a generic / `ModelViewSet` (below);
   set `permission_classes` and `@extend_schema`.
5. **URL** in `apps/<app>/urls.py` — `path()` for APIViews, a `DefaultRouter` for ViewSets.
6. **Mount** the app's `urls.py` in `config/urls.py` → `api_v1_patterns` (once per app).

## Import Paths

```python
# Views
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

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

> There is **no** `BaseARView` / `CustomResponse` / `CustomException` / `CamelCaseSerializer`
> / `required_resources` / resource-PK permissions / tenant headers in this project. If you
> see those in ported code, they belong to a different codebase — use the imports above.

## Response & Errors — the envelope is automatic

Every response is wrapped to `{data, meta, errors}` by
`apps/common/renderers.py::EnvelopeJSONRenderer` (default renderer) and
`apps/common/exceptions.py::envelope_exception_handler` (DRF `EXCEPTION_HANDLER`).

```python
# Success — return a plain Response; the renderer wraps it.
return Response(UserSerializer(user).data)                    # {data: {...}, meta: null, errors: null}
return Response(BusSerializer(bus).data, status=status.HTTP_201_CREATED)

# Error — just raise. The handler flattens it to [{code, field, detail}].
raise serializers.ValidationError("Invalid email or password.", code="invalid_credentials")
```

Rules:
- **Never** build the `{data, meta, errors}` dict by hand and **never** `try/except` to format
  errors in a view — raise and let the handler do it.
- **Always** attach a stable machine `code=` (`duplicate_plate`, `token_expired`,
  `invalid_driver`, …) so the frontend can branch on it.
- Lists routed through a pagination class are auto-wrapped to `{data: [...], meta: {pagination}}`.

## View Patterns

### Public read (generics)

```python
@extend_schema(tags=["routes"])
class RouteListView(ListAPIView):
    """GET /routes/ — list/search routes (public)."""

    queryset = Route.objects.all()
    serializer_class = RouteListSerializer
    permission_classes = [AllowAny]          # global default is IsAuthenticated — override for public
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "estimated_duration"]
```

### Admin CRUD (ModelViewSet + read/write serializer split + extra actions)

```python
@extend_schema_view(
    list=extend_schema(tags=["admin-buses"]),
    create=extend_schema(tags=["admin-buses"]),
    # … one per action you expose
)
class AdminBusViewSet(ModelViewSet):
    queryset = Bus.objects.select_related("assigned_driver")  # avoid N+1 on assigned_driver.email
    permission_classes = [IsAdmin]
    filterset_fields = ["status", "assigned_driver"]
    search_fields = ["plate"]
    ordering_fields = ["plate", "status", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return BusWriteSerializer
        return BusSerializer

    def create(self, request, *args, **kwargs):
        write = BusWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        bus = write.save()
        return Response(BusSerializer(bus).data, status=status.HTTP_201_CREATED)  # respond with the READ serializer

    @action(detail=True, methods=["patch"], url_path="assign-driver")
    def assign_driver(self, request, pk=None):
        bus = self.get_object()
        serializer = AssignDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bus = services.assign_driver(bus, serializer.validated_data["driver_id"])  # multi-step → service
        return Response(BusSerializer(bus).data)
```

### Custom flow (APIView)

Use `APIView` when there's no model-CRUD mapping (auth, token flows). Validate with a
serializer, do the work (or delegate to a service), return `Response`. See `apps/accounts/views.py`.

**Keep views thin:** validation in serializers, multi-step mutations in `services.py`, no manual
envelope. Declare `permission_classes` on **every** view.

## Serializer Conventions

- **Split read and write.** Read serializers set `read_only_fields = fields`. Write serializers
  expose only the writable fields.
- **Stable `code=`** on every `ValidationError`.
- **Mirror partial-unique constraints.** A `UniqueConstraint(condition=Q(is_deleted=False))` only
  covers active rows, so declare the field plainly (to suppress DRF's auto `UniqueValidator`) and
  check uniqueness in `validate_<field>` for a clean 400 instead of an `IntegrityError`:

```python
class BusWriteSerializer(serializers.ModelSerializer):
    plate = serializers.CharField(max_length=20)   # plain → no surprise auto-validator

    class Meta:
        model = Bus
        fields = ("plate", "capacity", "status", "assigned_driver")

    def validate_plate(self, value):
        qs = Bus.objects.filter(plate=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A bus with this plate already exists.", code="duplicate_plate")
        return value
```

- **Action payloads** are plain `serializers.Serializer` subclasses (e.g. `AssignDriverSerializer`,
  `AssignStopsSerializer`) — validate the input, let the view hand `validated_data` to a service.
- **Nested writes** that replace a set go through a service (`replace_route_stops`), not the serializer.
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

```python
# view / queryset
from django.db.models import Count, Exists, OuterRef
Route.objects.annotate(
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

```python
# view / queryset
from django.db.models import Prefetch
Route.objects.prefetch_related(
    Prefetch("stops", queryset=BusStop.objects.order_by("sequence"), to_attr="ordered_stops"),
)

# serializer — read the cached attr, no DB hit
def get_first_stop(self, obj):
    return obj.ordered_stops[0].name if obj.ordered_stops else None
```

Slice/iterate prefetched results **in Python** (`obj.ordered_stops[:5]`). Calling `.filter()` or
`.order_by()` on the prefetched manager **breaks the cache** and re-queries.

For forward FKs use `select_related` (e.g. `Bus.objects.select_related("assigned_driver")` so
`assigned_driver.email` is free — exactly what `AdminBusViewSet` does).

### 3. Compute in a service before serialization

For cross-row state or logic that's awkward in SQL, compute once in `services.py`, attach to each
instance (or pass a dict via serializer `context`), and read it in the serializer as a plain field.

### Allowed reads inside `get_<field>`

- Plain attribute access (`obj.field`, `obj.fk.field`) where the FK is `select_related`'d.
- Iterating an **already-prefetched** relation.
- Pure-Python computation on the instance (no ORM).

If you're writing `obj.<related>.count()/.filter()/.first()` or `Model.objects.filter(...)` inside a
serializer method, stop and pick fix #1, #2, or #3.

## Pagination

- **Default: `DefaultCursorPagination`** (cursor; stable under inserts; `page_size` 20, max 100,
  `?page_size=`, ordered `-created_at`). Applied globally via `REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]`.
- **`OffsetFallbackPagination`** for admin tables that need jump-to-page (page numbers + count).
  Set `pagination_class = OffsetFallbackPagination` on that view.
- Both tag their payload `__paginated__` so the envelope renderer lifts `results`/`pagination`
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
with a `code=` on bad input (see `StopListView` parsing `?near=lat,lng&radius=`). A `django_filters`
`FilterSet` is available if a view ever needs range/relational filters — add it then, scoped to that view.

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
      auth/   → apps.accounts.urls      (APIViews via path())
      ""      → apps.buses.urls         (DefaultRouter for ViewSets + path() for generics)
  /api/schema/  /api/docs/        → drf-spectacular
```

In an app's `urls.py`: set `app_name`, register ViewSets on a `DefaultRouter`
(`router.register("admin/buses", AdminBusViewSet, basename="admin-bus")`), add `path()` entries for
APIViews/generics, and end with `*router.urls`.

## Permissions / Auth (quick reference)

- Global default is `IsAuthenticated`. Override per view: `[AllowAny]` (public reads), `[IsAdmin]`,
  `[IsDriver]`, `[IsPassenger]`, or `[IsOwnerOrAdmin]` (set `owner_field` on the view).
- Auth is cookie-JWT (`CookieJWTAuthentication`, `st_access`/`st_refresh`) **or** a Bearer header.
  Tokens are issued/cleared only in `apps/accounts/views.py`; never put a JWT in a response body.
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
```

Tests use pytest + `APIClient`: `@pytest.mark.django_db`, role fixtures via
`User.objects.create_user(..., role=User.Roles.ADMIN)`, `client.force_authenticate(user=...)`, and
assertions on the **rendered envelope** — `resp.json()["data"]` / `["errors"]`, not `resp.data`.
See `apps/buses/tests/` and `apps/accounts/tests/test_auth.py`.

For deeper architecture, debugging, soft-delete/Celery questions, see the **`django-expert`** skill.
