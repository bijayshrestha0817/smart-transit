# Common Gotchas — Smart Transit AI

Every example below is grounded in this codebase (`backend/`). Wrong vs. right.

## Table of Contents
- [1. `User.objects` does NOT hide soft-deleted rows](#1-userobjects-does-not-hide-soft-deleted-rows)
- [2. Partial unique constraints need a serializer-level mirror](#2-partial-unique-constraints-need-a-serializer-level-mirror)
- [3. Never hand-build the envelope](#3-never-hand-build-the-envelope)
- [4. Missing transaction on multi-step mutations](#4-missing-transaction-on-multi-step-mutations)
- [5. Queries in serializers (N+1)](#5-queries-in-serializers-n1)
- [6. Throttle scopes are defined but not applied](#6-throttle-scopes-are-defined-but-not-applied)
- [7. Asserting on resp.data instead of resp.json()](#7-asserting-on-respdata-instead-of-respjson)
- [8. Soft delete vs. hard delete](#8-soft-delete-vs-hard-delete)
- [9. QueryDict multi-value params](#9-querydict-multi-value-params)

---

## 1. `User.objects` does NOT hide soft-deleted rows

Domain models inherit `TimeStampedSoftDeleteModel`, whose default `objects` manager
filters out `is_deleted=True`. **`User` is different** — it needs `UserManager` (for
`createsuperuser`), which does **not** filter. So a soft-deleted driver still appears
through `User.objects`.

**Wrong:**
```python
queryset = User.objects.filter(role=User.Roles.DRIVER)  # includes soft-deleted drivers
```

**Right:**
```python
# Filter is_deleted explicitly for any User query that should exclude deletions.
queryset = User.objects.filter(role=User.Roles.DRIVER, is_deleted=False)
```

(For domain models the reverse trap exists: `Model.objects` hides deleted rows —
use `Model.all_objects` when you deliberately need them.)

## 2. Partial unique constraints need a serializer-level mirror

Uniqueness is enforced by a **partial** constraint (`condition=Q(is_deleted=False)`),
so it only covers *active* rows and DRF's `ModelSerializer` may not auto-generate a
matching `UniqueValidator`. Relying on the DB alone yields an ugly 500 `IntegrityError`.

**Wrong:**
```python
class BusWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bus
        fields = ("plate", "capacity", "status", "assigned_driver")
    # plate collision with an active row → IntegrityError → 500
```

**Right:**
```python
class BusWriteSerializer(serializers.ModelSerializer):
    plate = serializers.CharField(max_length=20)  # plain field → no surprise auto-validator

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

## 3. Never hand-build the envelope

The `{data, meta, errors}` shape is applied by `EnvelopeJSONRenderer` (success) and
`envelope_exception_handler` (errors). Building it yourself produces a double-wrapped,
malformed response.

**Wrong:**
```python
return Response({"data": serializer.data, "meta": None, "errors": None})  # renderer wraps it AGAIN
# and:
try:
    ...
except ValidationError as e:
    return Response({"errors": [...]}, status=400)  # bypasses the handler, inconsistent shape
```

**Right:**
```python
return Response(serializer.data)                     # → {data: {...}, meta: null, errors: null}
# errors: just raise — the handler formats them.
raise serializers.ValidationError("…", code="…")     # → {data: null, meta: null, errors: [{code, field, detail}]}
```

## 4. Missing transaction on multi-step mutations

A mutation that touches more than one row/model must be atomic, or a mid-way failure
leaves the DB half-updated.

**Wrong:**
```python
def replace_route_stops(route, stops_data):
    route.stops.all().delete()                                   # succeeds
    return [BusStop.objects.create(route=route, **s) for s in stops_data]  # one raises → stops gone, none recreated
```

**Right:**
```python
def replace_route_stops(route, stops_data):
    with transaction.atomic():                                   # both happen, or neither
        route.stops.all().delete()                               # soft-delete (frees the unique sequences)
        return [BusStop.objects.create(route=route, **s) for s in stops_data]
```

Use the **context-manager** form (`with transaction.atomic():`) in service functions —
that's the project idiom, not the `@transaction.atomic` decorator.

## 5. Queries in serializers (N+1)

A `SerializerMethodField` that queries per object is fine on a single-object **detail**
view but explodes into N+1 on a **list** endpoint.

**Wrong (on a list endpoint):**
```python
class RouteListSerializer(serializers.ModelSerializer):
    stops = serializers.SerializerMethodField()

    def get_stops(self, obj):
        return BusStopSerializer(obj.stops.all().order_by("sequence"), many=True).data  # 1 query per route
```

**Right (prefetch at the queryset, read the cache in the serializer):**
```python
# View / queryset
Route.objects.prefetch_related(
    Prefetch("stops", queryset=BusStop.objects.order_by("sequence"))
)

# Serializer — iterate the prefetched cache (no new query)
def get_stops(self, obj):
    return BusStopSerializer(obj.stops.all(), many=True).data
```

For forward FKs use `select_related` — e.g. `AdminBusViewSet` uses
`Bus.objects.select_related("assigned_driver")` so serializing `assigned_driver.email`
costs no extra query.

## 6. Throttle scopes are defined but not applied

`DEFAULT_THROTTLE_RATES` defines `passenger` 100 / `driver` 300 / `admin` 500 per minute,
and `ScopedRateThrottle` is in the default throttle classes — but a scope is **inert
until a view names it**. Today only `AnonRateThrottle` (30/min) actually limits anything.

**Wrong (assuming the limit is already enforced):**
```python
class AdminRouteViewSet(ModelViewSet):
    permission_classes = [IsAdmin]
    # expecting 500/min — but no scope is set, so the admin rate never applies
```

**Right (opt the view into its scope):**
```python
class AdminRouteViewSet(ModelViewSet):
    permission_classes = [IsAdmin]
    throttle_scope = "admin"   # now the 500/min rate from settings applies
```

## 7. Asserting on `resp.data` instead of `resp.json()`

The envelope is applied at **render** time. In tests, `resp.data` is the raw,
pre-render serializer output (no envelope); `resp.json()` is the actual wire shape.

**Wrong:**
```python
assert resp.data["email"] == "new@example.com"      # raw serializer output — no {data: ...} wrapper
```

**Right:**
```python
assert resp.json()["data"]["email"] == "new@example.com"
assert any(e["field"] == "password" for e in resp.json()["errors"])
```

## 8. Soft delete vs. hard delete

`.delete()` is overridden to **soft**-delete. This is almost always what you want, but
know the escape hatches — and that deleting a `User` also deactivates the account.

```python
obj.delete()                       # soft: sets is_deleted=True (row stays)
Model.objects.filter(...).delete() # soft: SoftDeleteQuerySet.delete() marks the whole queryset
obj.hard_delete()                  # actually removes the row (admin/maintenance only)
user.delete()                      # soft delete + is_active=False → can no longer authenticate
```

## 9. QueryDict multi-value params

`request.query_params` is a `QueryDict`; `.dict()` keeps only the **last** value of a
repeated key. Use `getlist` for repeated params.

**Wrong:**
```python
statuses = request.query_params.dict().get("status")   # ?status=a&status=b → "b" only
```

**Right:**
```python
statuses = request.query_params.getlist("status")      # ["a", "b"]
```

(And when parsing a structured param like `?near=lat,lng`, validate and raise a clean
`ValidationError` with a `code=` — see `StopListView.get_queryset`.)
