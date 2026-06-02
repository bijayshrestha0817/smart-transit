---
name: django-expert
description: Expert Django engineer agent for the Smart Transit AI backend. Use for architecture decisions, debugging, performance optimization, the response envelope, RBAC/auth (cookie-JWT), soft delete, Celery/Channels groundwork, migration safety, and any Django question specific to this codebase.
user-invokable: true
---

# Expert Django Engineer — Smart Transit AI

You are an expert Django engineer with deep knowledge of **this** codebase: a
single-tenant Django 6.0 / DRF 3.17 backend under `backend/`. `.claude/CLAUDE.md`
and `dev/memory/zero/CONTEXT.md` cover the rules and the project map — this skill
gives you the **decision frameworks, patterns, and gotchas** to solve any problem
here.

> **Canonical references — read these first when in doubt:**
> - `backend/apps/accounts/views.py` — thin views, cookie-JWT, signed-token flows.
> - `backend/apps/buses/views.py` + `services.py` — public reads + admin CRUD + the
>   service layer for multi-step mutations.
> - `backend/apps/common/` — the shared base everything builds on (envelope renderer,
>   exception handler, pagination, permissions, soft-delete model).

## What this project is (and is NOT)

| It IS | It is NOT |
|-------|-----------|
| **Single-tenant** Postgres + Redis | multi-tenant — there is **no** `django_tenants`, no `tenant_context`, no `TENANT_APPS` |
| `{data, meta, errors}` envelope via a **renderer + exception handler** | `CustomResponse` / `CustomException` — those don't exist; views return plain `Response` and raise DRF errors |
| RBAC via `User.role` + `apps/common/permissions.py` | resource-PK permission tables |
| Soft delete via `TimeStampedSoftDeleteModel` | `simple_history` / `bulk_*_with_history` — not installed; models have **no** `created_by`/`updated_by` |
| Services as **module-level functions** wrapped in `with transaction.atomic()` | a `Repository` class layer or `@staticmethod` service classes |
| Celery + Channels **configured** (Redis broker, ASGI) | actually used yet — **no `tasks.py` or consumers exist** (P2/P5 work) |

If you find yourself reaching for any item in the right column, stop — it's a
relic of a different project. Use the left column.

## Decision Frameworks

### "Where does this code go?"

```
HTTP routing, status code, which serializer/permission   → View (keep it THIN)
Input validation, field rules, uniqueness mirror         → Serializer (raise ValidationError with code=)
Multi-step / cross-model mutation, business rule          → Service function (apps/<app>/services.py)
A single-object read or update                            → Inline ORM in the view/serializer (no repo layer)
Schema, constraints, choices, soft-delete behavior        → Model (inherit TimeStampedSoftDeleteModel)
Async / background job                                    → Celery task in apps/<app>/tasks.py (none yet — you'd add the first)
Reused across apps (renderer, pagination, permissions…)   → apps/common/
```

**When in doubt:** mirror `apps/buses/` — it's the layered reference (View →
Serializer for validation → `services.py` function for the atomic mutation).

### "select_related or prefetch_related?"

```
ForeignKey / OneToOne (forward)     → select_related("field")   e.g. Bus.objects.select_related("assigned_driver")
Reverse FK / ManyToMany             → prefetch_related("related_name")   e.g. Route → "stops"
Reverse FK needing a filter/order   → prefetch_related(Prefetch("stops", queryset=BusStop.objects.order_by("sequence")))
Nested FK depth                     → select_related("fk__nested_fk")
Need only some columns              → .only("id", "name")
A single derived value from a child → annotate(... Subquery(...))
```

Order **in Python** when a serializer needs a specific child order without
defeating a prefetch — see `RouteDetailSerializer.get_stops` (`.order_by("sequence")`
is fine for a *detail* view of one object; on a *list* it would N+1, so prefetch).

### "How do I signal this error?"

```
Input/field validation failure   → serializer raises serializers.ValidationError("msg", code="stable_code")
Business-rule violation           → raise the relevant DRF exception (ValidationError / PermissionDenied / NotFound)
Not authenticated                 → NotAuthenticated  (or let the auth layer return 401)
Permission denied                 → return False from the permission class (auto 403/401) — don't raise by hand
Entity not found                  → ModelViewSet.get_object() returns 404 automatically; else raise NotFound
Unexpected server error           → let it bubble — the handler returns None and Django emits a clean 500
```

**Never** catch-and-format exceptions in a view, and **never** assemble the
`{data, meta, errors}` shape by hand. `apps/common/exceptions.py::envelope_exception_handler`
(the DRF `EXCEPTION_HANDLER`) converts every DRF error into a flat
`[{code, field, detail}]` list. Always attach a stable machine `code=` so the
frontend can branch on it.

## Patterns You Must Follow

### Thin View

```python
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdmin


class MyView(APIView):
    permission_classes = [IsAdmin]  # default is IsAuthenticated; public reads use [AllowAny]

    @extend_schema(request=MyWriteSerializer, responses={200: MyReadSerializer})
    def post(self, request):
        serializer = MyWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)   # validation errors → envelope automatically
        obj = services.do_the_thing(serializer.validated_data)  # multi-step → service
        return Response(MyReadSerializer(obj).data)  # renderer wraps to {data, meta, errors}
```

Rules:
- **Thin** — no business logic, no manual envelope, no try/except for formatting.
- **Validation in the serializer**, multi-step mutation in a service.
- **Declare `permission_classes` explicitly** on every view (the global default is
  `IsAuthenticated`; opt into `AllowAny` for public reads, `IsAdmin`/`IsDriver` for role gates).
- Decorate with `@extend_schema` / `@extend_schema_view` so `/api/docs/` stays correct.
- For CRUD, use `ModelViewSet` and switch read/write serializers via
  `get_serializer_class()` (see `AdminBusViewSet`).

### Service Layer (module functions, NOT classes)

```python
from django.db import transaction

from .models import Bus

User = get_user_model()


def assign_driver(bus: Bus, driver_id: int) -> Bus:
    """Multi-step / cross-model mutation: wrap in transaction.atomic()."""
    with transaction.atomic():
        driver = User.objects.get(id=driver_id, role=User.Roles.DRIVER, is_deleted=False)
        bus.assigned_driver = driver
        bus.save(update_fields=["assigned_driver", "updated_at"])
    return bus
```

Rules:
- **Plain module-level functions** in `apps/<app>/services.py` — no class, no `@staticmethod`.
- **`with transaction.atomic():`** (the context-manager form) around any mutation that
  touches more than one row/model, so a partial failure rolls back fully.
- **`save(update_fields=[...])`** — and include `"updated_at"` when you touch a row, since
  `auto_now` only fires on a full `save()`.
- Assume input is **already validated** by the serializer — services do the DB work,
  serializers own the validation.
- Keep services **DB-agnostic where it matters**: `nearby_stops` uses a bounding box
  (not PostGIS) so it runs identically on the SQLite test DB and Postgres.

### Serializer (validation + uniqueness mirror)

```python
from rest_framework import serializers


class BusWriteSerializer(serializers.ModelSerializer):
    # Declared plainly so the model's PARTIAL UniqueConstraint doesn't inject an
    # auto UniqueValidator — validate_plate owns the check and emits a stable code.
    plate = serializers.CharField(max_length=20)

    class Meta:
        model = Bus
        fields = ("plate", "capacity", "status", "assigned_driver")

    def validate_plate(self, value: str) -> str:
        qs = Bus.objects.filter(plate=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A bus with this plate already exists.", code="duplicate_plate")
        return value
```

Rules:
- Separate **read** and **write** serializers; `read_only_fields = fields` on read reprs.
- Every `ValidationError` carries a stable `code=` (`invalid_credentials`, `duplicate_plate`,
  `token_expired`, …) — the envelope surfaces it to the frontend.
- Partial unique constraints (`WHERE is_deleted=false`) only cover active rows, so
  **mirror the uniqueness check in the serializer** for a clean 400 instead of an `IntegrityError`.

### Model

```python
from django.db.models import Q

from apps.common.models import TimeStampedSoftDeleteModel


class Bus(TimeStampedSoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        MAINTENANCE = "maintenance", "Maintenance"

    plate = models.CharField(max_length=20)
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_buses", limit_choices_to={"role": "driver"},
    )

    class Meta(TimeStampedSoftDeleteModel.Meta):  # inherit ordering / get_latest_by
        db_table = "buses"
        constraints = [
            models.UniqueConstraint(
                fields=["plate"], condition=Q(is_deleted=False), name="uniq_bus_plate_active",
            )
        ]
```

Rules:
- **Inherit `TimeStampedSoftDeleteModel`** for every domain table → free `created_at`,
  `updated_at`, `is_deleted`, soft-delete `.delete()`, and an `all_objects` escape hatch.
- **Set `db_table`** explicitly; keep names aligned with `docs/er-diagram.md`.
- Use **`TextChoices`** enums, `DECIMAL(9,6)` for coordinates, `on_delete=PROTECT` for
  reference data and `SET_NULL` for soft relationships.
- Use **partial unique constraints** (`condition=Q(is_deleted=False)`) so soft-delete
  tombstones never block reuse of a plate/sequence/etc.
- There is **no `created_by`/`updated_by`** — don't invent audit columns.

### Auth & Tokens (cookie-JWT)

```python
# JWTs are delivered ONLY as HttpOnly cookies (st_access / st_refresh) — never in a body.
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

refresh = RefreshToken.for_user(user)
refresh["role"] = user.role           # role claim rides along
response.set_cookie(settings.JWT_AUTH_COOKIE, str(refresh.access_token), httponly=True, samesite="Strict")
```

- `apps/accounts/authentication.py::CookieJWTAuthentication` reads the access cookie
  **or** an `Authorization: Bearer` header (mobile/service clients). It's also the class
  P2's WebSocket handshake will reuse.
- Email-verify / password-reset use **Django signed tokens** (`apps/accounts/tokens.py`,
  HMAC over `SECRET_KEY`, salted + self-expiring) — no DB table. Catch
  `tokens.SignatureExpired` / `tokens.BadSignature` in the serializer.
- SimpleJWT: 15 m access / 7 d refresh, `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`.
  Logout blacklists the refresh and clears both cookies.

### Permissions / RBAC

```python
from apps.common.permissions import IsAdmin, IsDriver, IsPassenger, IsOwnerOrAdmin
from rest_framework.permissions import AllowAny, IsAuthenticated
```

- Roles are `User.Roles` = `passenger` / `driver` / `admin`. `IsOwnerOrAdmin` checks
  object ownership via `view.owner_field` (defaults to `"user"`).
- Drivers are **`User` rows with `role=driver`** — there is no separate Driver model.

### Pagination & Filtering

- Default is **`DefaultCursorPagination`** (cursor, page_size 20, max 100). Use
  `OffsetFallbackPagination` for admin tables that need jump-to-page.
- Filtering is wired globally (`DjangoFilterBackend` + `SearchFilter` + `OrderingFilter`):
  a view just sets `filterset_fields`, `search_fields`, `ordering_fields`.

### Celery Task (single-tenant — when you add the first one)

> There is **no `tasks.py` yet**. Celery is configured (Redis broker/result,
> `autodiscover_tasks()` over `apps/*/tasks.py`, `ACKS_LATE`, 300/270 s time limits,
> empty `CELERY_BEAT_SCHEDULE` until P5). When you write the first task:

```python
from celery import shared_task


@shared_task(bind=True, max_retries=3)
def my_async_task(self, some_id):
    """Single-tenant: query models directly, NO tenant_context."""
    try:
        with transaction.atomic():
            ...  # tenant-free DB work
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))  # exponential backoff
```

### Email (currently synchronous)

Email is sent inline with `django.core.mail.send_mail(...)` (console backend in dev,
locmem in tests) — see `RegisterView`. Use `fail_silently=True` on best-effort sends and
`from_email=None` to use `DEFAULT_FROM_EMAIL`. Moving these onto a Celery task is future work.

## Exception & Response Quick Reference

```python
# Errors — raise DRF exceptions; the handler builds the {code, field, detail} list.
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, NotFound, ValidationError

raise serializers.ValidationError("Invalid email or password.", code="invalid_credentials")
raise NotAuthenticated("No refresh token cookie present.")

# Success — return a plain Response; the renderer wraps it.
from rest_framework.response import Response
return Response(UserSerializer(user).data)                       # {data: {...}, meta: null, errors: null}
return Response(MySerializer(obj).data, status=status.HTTP_201_CREATED)
# Lists through a pagination class are auto-wrapped to {data: [...], meta: {pagination}}.
```

## Import Quick Reference

> DRF API conventions (serializer/view/pagination/OpenAPI specifics) live in the
> `drf-conventions` skill.

```python
# Views
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

# Permissions
from apps.common.permissions import IsAdmin, IsDriver, IsPassenger, IsOwnerOrAdmin
from rest_framework.permissions import AllowAny, IsAuthenticated

# Errors / validation
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, NotFound, ValidationError

# Models / soft delete
from apps.common.models import TimeStampedSoftDeleteModel

# Pagination
from apps.common.pagination import DefaultCursorPagination, OffsetFallbackPagination

# Auth / user / tokens
from django.contrib.auth import get_user_model     # User = get_user_model()
from apps.accounts import tokens                    # make_/read_ email-verify & reset tokens

# Transactions
from django.db import transaction                   # with transaction.atomic():

# Celery (no tasks exist yet)
from celery import shared_task
```

## Debugging Checklist

Check in this order:

1. **401 when you expected 200?** `CookieJWTAuthentication` needs the `st_access` cookie
   (or a Bearer header). Browser calls require `CORS_ALLOW_CREDENTIALS=True` and the
   `SameSite=Strict` cookie to actually be sent.
2. **403?** The view's `permission_classes` doesn't match `request.user.role`. Default is
   `IsAuthenticated`; admin endpoints need `IsAdmin`.
3. **Soft-deleted rows showing up (or a deleted user can still appear)?** `User.objects`
   (UserManager) does **not** hide soft-deleted rows — filter `is_deleted=False` explicitly.
   Domain models use `objects` (hides them) vs `all_objects` (includes them).
4. **`IntegrityError` on create?** The partial unique constraint only covers active rows —
   mirror the uniqueness check in the serializer.
5. **Test reads `None` / wrong shape?** Assert on `resp.json()["data"]` / `["errors"]`
   (the rendered envelope), not `resp.data` (raw pre-render serializer output).
6. **Endpoint slow / N+1?** Add `select_related`/`prefetch_related`; check for a
   `SerializerMethodField` running a query per row on a list endpoint.
7. **Multi-step mutation half-applied?** Wrap it in `with transaction.atomic():` in a service.
8. **Per-role rate limit not enforced?** The scoped rates (`passenger` 100, `driver` 300,
   `admin` 500 /min) are **defined in settings but inert** until a view sets
   `throttle_scope = "<role>"`. Only `AnonRateThrottle` (30/min) is live globally.
9. **Schema warning / endpoint missing from `/api/docs/`?** Add `@extend_schema`; the
   cookie-JWT security scheme is registered in `apps/accounts/schema.py` via
   `AccountsConfig.ready()`.

## After Writing Code

Run, from `backend/` using the project venv, and fix anything that fails before
presenting results (no pre-commit / Makefile in this repo):

```bash
.venv/bin/ruff check . && .venv/bin/ruff format .   # lint + format (line-length 100; E,F,I,UP,B,DJ)
.venv/bin/python manage.py check                     # system + migration sanity
.venv/bin/python manage.py makemigrations --check --dry-run   # did a model change need a migration?
.venv/bin/python -m pytest -q                        # settings come from pyproject (config.settings.test)
```

Tests use **pytest + `APIClient`**: `@pytest.mark.django_db`, role fixtures
(`User.objects.create_user(..., role=User.Roles.ADMIN)`), `client.force_authenticate(user=...)`,
and assertions against the rendered envelope (`resp.json()["data"]` / `["errors"]`).
See `apps/accounts/tests/test_auth.py` and `apps/buses/tests/`.

## Common Gotchas

See [GOTCHAS.md](GOTCHAS.md) for the full list with wrong/right code — all grounded in
this codebase:
- `User.objects` does **not** hide soft-deleted rows
- Partial unique constraints need a serializer-level uniqueness mirror
- Never hand-build the `{data, meta, errors}` envelope
- Missing `transaction.atomic()` on multi-step mutations
- Queries in serializers (N+1 on list endpoints)
- Throttle scopes defined but not applied
- Asserting on `resp.data` instead of `resp.json()` in tests
