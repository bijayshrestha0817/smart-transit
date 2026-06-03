---
name: n-plus-one-detector
description: Scans a specific view or queryset and suggests where to implement select_related or prefetch_related to optimize database performance based on the accessed fields.
user-invokable: true
---

# N+1 Query Detector — Smart Transit AI

`.claude/CLAUDE.md`, `django-expert`, and `drf-conventions` cover the architecture. This
skill is the **analysis workflow** for finding and fixing N+1 query issues in this codebase.

> **Where queries live here:** this project uses a **layered architecture** —
> `View → Service (optional) → Repository → Model`. All ORM lives exclusively in
> `apps/<app>/repository/<Model>Repository.py` (one class per model, PascalCase filename,
> inheriting `BaseRepository` from `apps/common/repository/base.py`). Optimizations
> (`select_related`/`prefetch_related`/`annotate`) go in the **repository's queryset
> methods** — never in the view, never in a serializer method. Views call a repository
> method and return the resulting queryset; serializers read whatever was prefetched.

## When to Use

- Check a view, serializer, or queryset for N+1 queries
- Optimize DB performance for an endpoint
- Review a new/modified queryset that returns related objects

## Step 1: Identify the Target Endpoint

Trace the request path from URL to database (4 layers):

1. **View** — find the view class/method (`apps/<app>/v1/views/<Domain>Views.py`). Its
   `get_queryset()` returns a repository queryset; views themselves contain no ORM.
2. **Service** *(optional)* — if the view delegates writes/logic to
   `apps/<app>/v1/service/<Domain>Service.py`, read that class for any cross-row
   query calls.
3. **Repository** — the real queryset owner: `apps/<app>/repository/<Model>Repository.py`.
   This is where `select_related`, `prefetch_related`, and `annotate` are defined.
4. **Serializer** — the response serializer and any nested serializers
   (`apps/<app>/v1/serializers/<Model>Serializer.py`). It reads fields/attributes; it must
   not issue any ORM calls.

The N+1 risk lives in the gap between what the **serializer accesses** and what the
**repository's queryset method prefetches**.

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

## Step 3: Audit the Repository Queryset

Read the repository class (`apps/<app>/repository/<Model>Repository.py`) that the view
calls and extract the queryset method's actual content:

1. **`select_related()`** paths — e.g. `BusRepository.active()` returns
   `Bus.objects.select_related("assigned_driver")`.
2. **`prefetch_related()`** paths, including custom `Prefetch` objects — e.g.
   `RouteRepository.detail_queryset()` uses
   `Prefetch("stops", queryset=BusStop.objects.order_by("sequence"), to_attr="ordered_stops")`.
3. **Annotations / Subqueries** — computed at the DB (no N+1 risk). These also belong
   in the repository.
4. **`only()` / `defer()`** field restrictions.

## Step 4: Diff and Report

Compare serializer access (Step 2) against queryset optimization (Step 3):

```
## N+1 Query Analysis: <ViewClass.method>

### Request Path
View:       apps/<app>/v1/views/<Domain>Views.py → <ViewClass> (get_queryset)
Service:    apps/<app>/v1/service/<Domain>Service.py → <ClassName>   (if any)
Repository: apps/<app>/repository/<Model>Repository.py → <RepositoryClass>.<method>
Serializer: apps/<app>/v1/serializers/<Model>Serializer.py → <SerializerClass>

### Findings
| # | Severity | Relation Path | Accessed By | Fix |
|---|----------|---------------|-------------|-----|
| 1 | HIGH   | assigned_driver | BusSerializer.assigned_driver_email (source) | add to select_related in BusRepository.active() |
| 2 | MEDIUM | stops           | RouteDetailSerializer.get_stops (method)     | add Prefetch in RouteRepository.detail_queryset() |

### Already Optimized
- assigned_driver — select_related ✓   (BusRepository.active())

### Suggested Fix
<exact queryset change in the repository method — NOT in the view>
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
   inside `get_<field>`. Fix: move logic to a `Prefetch`/`annotate` in the repository method, then
   read the prefetched attribute in the serializer (e.g. `getattr(obj, "ordered_stops", [])`).
2. **Bare repository queryset** — `Model.objects.all()` (or `Model.objects.filter(...)` without
   optimizations) while the serializer touches relations. Fix: add `select_related`/`prefetch_related`
   to the relevant repository queryset method. Never add ORM calls to the view itself.
3. **Missing FK depth** — `select_related("a")` when the serializer reads `a.b.field`. Fix: `select_related("a__b")` in the repository.
4. **String prefetch where a filter/order is needed** — use `Prefetch(..., queryset=...)` in the repository instead of a plain string.
5. **Annotation opportunity** — a `SerializerMethodField` doing a simple count/exists that a single
   `Count`/`Exists` annotation would replace. Annotation belongs in the repository.

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

> Real example: `RouteDetailSerializer.get_stops` reads `getattr(obj, "ordered_stops", [])` —
> a Python attribute, no DB hit — because `RouteRepository.detail_queryset()` already prefetched
> `Prefetch("stops", queryset=BusStop.objects.order_by("sequence"), to_attr="ordered_stops")`.
> This is the correct pattern. If a future serializer were to call `obj.stops.all().order_by("sequence")`
> instead, it would be a HIGH-severity N+1 on a list endpoint → fix by ensuring the repository
> sets `to_attr` and the serializer reads the attribute.

For full fix patterns (annotate vs prefetch vs compute-in-service), see
`drf-conventions` → "SerializerMethodField — N+1 Rules".

## Rules

1. **Fix in the repository layer** — optimizations go in the **model repository's queryset methods**
   (`apps/<app>/repository/<Model>Repository.py`). Never add `select_related`/`prefetch_related` to
   the view or the serializer. For cross-row computation (annotations, subqueries), the repository is
   still the right place; the service may call a repository method to obtain an annotated queryset.
2. **Trace the real code** — read the actual view, repository, service, and serializer before
   reporting. Don't guess.
3. **List vs detail matters** — a missing `select_related` on a list endpoint (N rows) is HIGH; on a
   detail endpoint (1 row) it's MEDIUM.
4. **Count queries, not relations** — a `SerializerMethodField` running a query per row is worse than a
   single missing `select_related`.
5. **Preserve existing optimizations** — show the full updated `select_related`/`prefetch_related` call
   inside the repository method, not just the new paths.

## Project-Specific Patterns

The domain is small today (`Route`, `BusStop`, `Bus`, `User`), so the useful chains are short.
These patterns are grounded in the real repository classes:

```python
# apps/buses/repository/BusRepository.py — BusRepository.active()
# assigned_driver is a forward FK shown via BusSerializer.assigned_driver_email
# (source="assigned_driver.email") — must be selected or every row hits the DB.
Bus.objects.select_related("assigned_driver")   # already in BusRepository.active()

# apps/buses/repository/RouteRepository.py — RouteRepository.detail_queryset()
# Route detail needs stops in sequence order; to_attr avoids a second .order_by() in
# the serializer. RouteDetailSerializer.get_stops reads getattr(obj, "ordered_stops", []).
from django.db.models import Prefetch
Route.objects.prefetch_related(
    Prefetch(
        "stops",
        queryset=BusStop.objects.order_by("sequence"),
        to_attr="ordered_stops",
    )
)

# Annotation example (add to RouteRepository if needed by a list serializer)
# Avoids one COUNT and one EXISTS per row on list endpoints.
from django.db.models import Count, Exists, OuterRef
Route.objects.annotate(
    stop_count=Count("stops"),
    has_stops=Exists(BusStop.objects.filter(route=OuterRef("pk"))),
)
```

All three patterns belong **in the repository** — the view's `get_queryset()` simply
returns `RouteRepository.detail_queryset()` or `BusRepository.active()` without adding
any ORM calls.

### Discover Hotspots Live

Don't trust a hardcoded list — it rots as fixes land and as new apps (`trips`, `tickets`, …) arrive.
Grep the **layered paths** (there are no flat `apps/<app>/serializers.py`/`views.py`/`services.py`
files — all ORM is split across `v1/serializers/`, `v1/views/`, `v1/service/`, and `repository/`),
then trace each candidate through Steps 1–6:

```bash
# from backend/ — SerializerMethodField / serializer bodies hitting the DB (highest yield)
git grep -nE 'obj\.\w+\.(filter|first|last|count|exists|order_by|aggregate)\(' -- 'apps/*/v1/serializers/*.py'
git grep -nE '\.objects\.(filter|get|first|count|exists)\(' -- 'apps/*/v1/serializers/*.py'

# Repository querysets returning related objects with no select_related/prefetch_related
git grep -nE '\.objects\.(all|filter)\(' -- 'apps/*/repository/*.py'

# ORM that leaked OUT of the repository (it shouldn't be in a view or service)
git grep -nE '\.objects\.(get|first|filter|all)\(' -- 'apps/*/v1/views/*.py' 'apps/*/v1/service/*.py'
```

Order findings by blast radius: **list endpoints first** (every issue × `page_size`), then **detail**
endpoints, then **Celery tasks** that loop over many rows (none exist yet — relevant from P2+).

Skip false positives: `obj.related.all()` after `prefetch_related("related")` is fine — verify against
the repository queryset method before flagging.
