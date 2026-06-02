---
name: n-plus-one-detector
description: Scans a specific view or queryset and suggests where to implement select_related or prefetch_related to optimize database performance based on the accessed fields.
user-invokable: true
---

# N+1 Query Detector — Smart Transit AI

`.claude/CLAUDE.md`, `django-expert`, and `drf-conventions` cover the architecture. This
skill is the **analysis workflow** for finding and fixing N+1 query issues in this codebase.

> **Where queries live here:** this project has a flat layout — `apps/<app>/{views,serializers,services,models}.py`.
> There is **no `repository/` layer**. A queryset is defined on the **view** (`queryset = …`
> or `get_queryset()`); optimizations (`select_related`/`prefetch_related`/`annotate`) go
> **there**, or — for cross-row logic — in a `services.py` function. Never put query logic in a
> serializer method.

## When to Use

- Check a view, serializer, or queryset for N+1 queries
- Optimize DB performance for an endpoint
- Review a new/modified queryset that returns related objects

## Step 1: Identify the Target Endpoint

Trace the request path from URL to database (3 hops here, not 4 — no repository):

1. **View** — find the view class/method (`apps/<app>/views.py`) and its `queryset` / `get_queryset()`.
2. **Service** *(optional)* — if the view delegates to `apps/<app>/services.py`, read that function.
3. **Serializer** — the response serializer and any nested serializers (`apps/<app>/serializers.py`).

The N+1 risk lives in the gap between what the **serializer accesses** and what the
**view's queryset prefetches**.

## Step 2: Map Serializer Field Access

Classify every serializer field that touches a relationship:

| Access Type | Example (this codebase) | Optimization |
|-------------|-------------------------|--------------|
| `source="fk.field"` | `BusSerializer.assigned_driver_email = CharField(source="assigned_driver.email")` | `select_related("assigned_driver")` |
| Nested serializer (FK/O2O) | `driver = DriverSerializer()` | `select_related("<fk>")` |
| Nested serializer (reverse FK/M2M) | `stops = BusStopSerializer(many=True)` | `prefetch_related("stops")` |
| `SerializerMethodField` → related obj | `obj.assigned_driver.email` | `select_related("assigned_driver")` |
| `SerializerMethodField` → queryset | `obj.stops.order_by("sequence")` | `prefetch_related` (or annotate) |

Build the list of **all relation paths the serializer will trigger**.

## Step 3: Audit the View's Queryset

Read the view's `queryset` / `get_queryset()` and extract:

1. **`select_related()`** paths (e.g. `AdminBusViewSet` → `Bus.objects.select_related("assigned_driver")`).
2. **`prefetch_related()`** paths, including custom `Prefetch` objects.
3. **Annotations / Subqueries** — computed at the DB (no N+1 risk).
4. **`only()` / `defer()`** field restrictions.

## Step 4: Diff and Report

Compare serializer access (Step 2) against queryset optimization (Step 3):

```
## N+1 Query Analysis: <ViewClass.method>

### Request Path
View:       apps/<app>/views.py → <ViewClass> (queryset / get_queryset)
Service:    apps/<app>/services.py → <function>   (if any)
Serializer: apps/<app>/serializers.py → <SerializerClass>

### Findings
| # | Severity | Relation Path | Accessed By | Fix |
|---|----------|---------------|-------------|-----|
| 1 | HIGH   | assigned_driver | BusSerializer.assigned_driver_email (source) | add to select_related |
| 2 | MEDIUM | stops           | RouteDetailSerializer.get_stops (method)     | prefetch_related |

### Already Optimized
- assigned_driver — select_related ✓   (AdminBusViewSet)

### Suggested Fix
<exact queryset change on the view (or get_queryset)>
```

### Severity Levels

| Level | Meaning |
|-------|---------|
| **HIGH** | Fires on every item of a **list** endpoint (multiplied by `page_size`) — guaranteed N+1 |
| **MEDIUM** | Conditional, or on a **detail** endpoint (single row) — likely N+1 |
| **LOW** | Rare, or already mitigated by an annotation |
| **OK** | Already optimized |

## Step 5: Check for Anti-Patterns

1. **Query in a serializer method** — any `.objects.filter()/.get()/.first()` or `obj.<related>.filter()`
   inside `get_<field>`. Fix: move to a queryset `annotate`/`Prefetch`, or compute in a service.
2. **Bare view queryset** — `queryset = Model.objects.all()` while the serializer touches relations.
   Fix: add `select_related`/`prefetch_related` to the view's `queryset`/`get_queryset()`.
3. **Missing FK depth** — `select_related("a")` when the serializer reads `a.b.field`. Fix: `select_related("a__b")`.
4. **String prefetch where a filter/order is needed** — use `Prefetch(..., queryset=...)` instead.
5. **Annotation opportunity** — a `SerializerMethodField` doing a simple count/exists that a single
   `Count`/`Exists` annotation would replace.

## Step 6: Scan SerializerMethodField Bodies (highest-yield)

`SerializerMethodField` is the most common N+1 source. For each `get_<field>`:

| Red flag | Why it's N+1 | Fix |
|---|---|---|
| `obj.<related>.count()` | one COUNT per row | `Count(...)` annotation |
| `obj.<related>.exists()` | one SELECT per row | `Exists(...)` annotation |
| `obj.<related>.first()/.last()` | one SELECT per row | `Subquery`, or `Prefetch` then `[0]` in Python |
| `obj.<related>.filter(...)` | one SELECT per row | `Prefetch(..., queryset=...)`, slice in Python |
| `obj.<related>.order_by(...).first()` | one SELECT per row | `Subquery` annotation |
| `Model.objects.filter(...)` | one SELECT per row | queryset annotation/prefetch |
| `obj.<related>.aggregate(...)` | one aggregation per row | `Sum`/`Avg`/… annotation |

`obj.<related>.all()` **after** a matching `prefetch_related("<related>")` is fine. Plain
attribute access (`obj.fk.field`) is fine when the FK is `select_related`'d — just confirm the chain.

> Real example: `RouteDetailSerializer.get_stops` does `obj.stops.all().order_by("sequence")`. On the
> **detail** view (one Route) that's one extra query — acceptable. If the same serializer were used on
> a **list**, it'd be HIGH-severity N+1 → prefetch `Prefetch("stops", queryset=BusStop.objects.order_by("sequence"))`.

For full fix patterns (annotate vs prefetch vs compute-in-service), see
`drf-conventions` → "SerializerMethodField — N+1 Rules".

## Rules

1. **Fix at the queryset** — optimizations go on the **view's `queryset`/`get_queryset()`** (or a
   `services.py` function for cross-row computation). Never add query logic to serializer methods.
2. **Trace the real code** — read the actual view, service, and serializer before reporting. Don't guess.
3. **List vs detail matters** — a missing `select_related` on a list endpoint (N rows) is HIGH; on a
   detail endpoint (1 row) it's MEDIUM.
4. **Count queries, not relations** — a `SerializerMethodField` running a query per row is worse than a
   single missing `select_related`.
5. **Preserve existing optimizations** — show the full updated `select_related`/`prefetch_related` call,
   not just the new paths.

## Project-Specific Patterns

The domain is small today (`Route`, `BusStop`, `Bus`, `User`), so the useful chains are short:

```python
# Buses list/detail — driver is a forward FK shown via assigned_driver_email
Bus.objects.select_related("assigned_driver")               # AdminBusViewSet already does this

# Routes list — counts/booleans as annotations (no per-row queries)
from django.db.models import Count, Exists, OuterRef
Route.objects.annotate(
    stop_count=Count("stops"),
    has_stops=Exists(BusStop.objects.filter(route=OuterRef("pk"))),
)

# Route detail — ordered child rows via a filtered Prefetch
from django.db.models import Prefetch
Route.objects.prefetch_related(
    Prefetch("stops", queryset=BusStop.objects.order_by("sequence"), to_attr="ordered_stops"),
)
# serializer then reads obj.ordered_stops (no DB hit)
```

### Discover Hotspots Live

Don't trust a hardcoded list — it rots as fixes land and as new apps (`trips`, `tickets`, …) arrive.
Grep, then trace each candidate through Steps 1–6:

```bash
# from backend/ — SerializerMethodField / serializer bodies hitting the DB (highest yield)
git grep -nE 'obj\.\w+\.(filter|first|last|count|exists|order_by|aggregate)\(' -- 'apps/*/serializers.py'
git grep -nE '\.objects\.(filter|get|first|count|exists)\(' -- 'apps/*/serializers.py'

# View querysets with no select_related/prefetch_related while serializing relations
git grep -nE 'queryset = \w+\.objects\.(all|filter)\(' -- 'apps/*/views.py'
git grep -nE '\.objects\.(get|first)\(' -- 'apps/*/services.py'
```

Order findings by blast radius: **list endpoints first** (every issue × `page_size`), then **detail**
endpoints, then **Celery tasks** that loop over many rows (none exist yet — relevant from P2+).

Skip false positives: `obj.related.all()` after `prefetch_related("related")` is fine — verify against
the view's queryset before flagging.
