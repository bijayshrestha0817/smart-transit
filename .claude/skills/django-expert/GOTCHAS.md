# Common Gotchas — Smart Transit AI

Every example is grounded in this codebase (layered `View → Service → Repository → Model`).
Wrong vs. right.

## Table of Contents
- [1. `User.objects` does NOT hide soft-deleted rows](#1-userobjects-does-not-hide-soft-deleted-rows)
- [2. Partial unique constraints need a serializer mirror (via the repository)](#2-partial-unique-constraints-need-a-serializer-mirror-via-the-repository)
- [3. Never hand-build the envelope](#3-never-hand-build-the-envelope)
- [4. Missing transaction in a service](#4-missing-transaction-in-a-service)
- [5. N+1 — fix it in the repository, not the serializer](#5-n1--fix-it-in-the-repository-not-the-serializer)
- [6. ORM leaking out of the repository](#6-orm-leaking-out-of-the-repository)
- [7. Throttle scopes are defined but not applied](#7-throttle-scopes-are-defined-but-not-applied)
- [8. Asserting on resp.data instead of resp.json()](#8-asserting-on-respdata-instead-of-respjson)
- [9. Soft delete vs. hard delete](#9-soft-delete-vs-hard-delete)

---

## 1. `User.objects` does NOT hide soft-deleted rows

Domain models inherit `TimeStampedSoftDeleteModel`, whose `objects` manager filters out
`is_deleted=True`. **`User` uses `UserManager`** (for `createsuperuser`), which does **not**.

**Wrong:**
```python
# in DriverRepository / AccountRepository
return User.objects.filter(role=User.Roles.DRIVER)   # includes soft-deleted drivers
```

**Right:**
```python
return User.objects.filter(role=User.Roles.DRIVER, is_deleted=False)   # DriverRepository.active_drivers()
```

(For domain models the reverse trap: `Model.objects` hides deleted rows — use `Model.all_objects`
when you deliberately need them.)

## 2. Partial unique constraints need a serializer mirror (via the repository)

Uniqueness is a **partial** constraint (`condition=Q(is_deleted=False)`) — only active rows. Relying
on the DB alone yields an ugly 500 `IntegrityError`. Mirror the check in the serializer, querying
through the **repository** (serializers don't touch the ORM directly).

**Right:**
```python
class BusWriteSerializer(serializers.ModelSerializer):
    plate = serializers.CharField(max_length=20)   # plain → no surprise auto-validator

    def validate_plate(self, value):
        exclude_pk = self.instance.pk if self.instance is not None else None
        if BusRepository.plate_exists(value, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A bus with this plate already exists.", code="duplicate_plate")
        return value
```

## 3. Never hand-build the envelope

Success responses are built by **`CustomResponse`**; errors by **`CustomException`** /
`serializers.ValidationError` → `envelope_exception_handler`. Building `{data, meta, errors}` by hand
double-wraps or diverges.

**Wrong:**
```python
return CustomResponse({"data": serializer.data, "meta": None, "errors": None})  # double-shaped
return Response({"errors": [...]}, status=400)                                   # bypasses the handler
```

**Right:**
```python
return CustomResponse(serializer.data)                       # → {data: {...}, meta: null, errors: null}
raise CustomException(message="…", status=404, code="…")     # service-side; handler builds the error envelope
raise serializers.ValidationError("…", code="…")             # validation; handler builds the error envelope
```

## 4. Missing transaction in a service

A service mutation touching more than one row/model must be atomic.

**Wrong:**
```python
class RouteService:
    @staticmethod
    def replace_stops(route, stops_data):
        BusStopRepository.delete_for_route(route)                       # succeeds
        return BusStopRepository.bulk_create_for_route(route, stops_data)  # one raises → stops gone, none recreated
```

**Right:**
```python
class RouteService:
    @staticmethod
    def replace_stops(route, stops_data):
        with transaction.atomic():                                      # both, or neither
            BusStopRepository.delete_for_route(route)
            return BusStopRepository.bulk_create_for_route(route, stops_data)
```

## 5. N+1 — fix it in the repository, not the serializer

A `SerializerMethodField` querying per object is N+1 on a list. The fix lives in the **repository's
queryset method**; the serializer reads the prefetched attribute.

**Wrong (ORM in the serializer):**
```python
def get_stops(self, obj):
    return BusStopSerializer(obj.stops.all().order_by("sequence"), many=True).data   # 1 query per route
```

**Right (prefetch in the repository, read the attr in the serializer):**
```python
# RouteRepository.detail_queryset()
return Route.objects.prefetch_related(
    Prefetch("stops", queryset=BusStop.objects.order_by("sequence"), to_attr="ordered_stops")
)
# RouteDetailSerializer
def get_stops(self, obj):
    return BusStopSerializer(getattr(obj, "ordered_stops", []), many=True).data       # no query
```

Forward FKs: `BusRepository.active()` uses `select_related("assigned_driver")` so
`BusSerializer.assigned_driver_email` is free. (See the `n-plus-one-detector` skill.)

## 6. ORM leaking out of the repository

ALL ORM belongs in the repository (class per model). Views and services must not query directly; a
serializer must not either (uniqueness/lookup goes through a repository method).

**Wrong:**
```python
class BusService:
    @staticmethod
    def assign_driver(bus, driver_id):
        driver = User.objects.get(id=driver_id, role=User.Roles.DRIVER)   # ORM in the service
```

**Right:**
```python
class BusService:
    @staticmethod
    def assign_driver(bus, driver_id):
        driver = DriverRepository.get_driver(driver_id)                   # repository owns the query
        if driver is None:
            raise CustomException(message="No active driver with this id.", status=404, code="invalid_driver")
```

## 7. Throttle scopes are defined but not applied

`DEFAULT_THROTTLE_RATES` defines `passenger`/`driver`/`admin` rates and `ScopedRateThrottle` is in the
defaults — but a scope is **inert until a view names it**. Today only `AnonRateThrottle` (30/min) limits.

**Right:**
```python
class AdminRouteViewSet(ModelViewSet):
    permission_classes = [IsAdmin]
    throttle_scope = "admin"   # now the 500/min rate from settings applies
```

## 8. Asserting on `resp.data` instead of `resp.json()`

The envelope exists at the wire level. `resp.data` is raw pre-render output; `resp.json()` is the
actual shape.

**Right:**
```python
assert resp.json()["data"]["email"] == "new@example.com"
assert any(e["field"] == "password" for e in resp.json()["errors"])
```

## 9. Soft delete vs. hard delete

`.delete()` is overridden to **soft**-delete; deleting a `User` also deactivates it.

```python
obj.delete()                        # soft: sets is_deleted=True
Model.objects.filter(...).delete()  # soft: SoftDeleteQuerySet marks the whole queryset
obj.hard_delete()                   # actually removes the row (admin/maintenance only)
user.delete()                       # soft delete + is_active=False → can no longer authenticate
```
