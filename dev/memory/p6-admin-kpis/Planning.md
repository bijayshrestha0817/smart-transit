# Plan — P6 admin KPI/overview endpoint

Status: DONE (implemented + verified; not committed — awaiting user to ship)
Decisions (resolved 2026-06-11): KPI breadth = rich set; trip counts = BOTH lifetime +
today (`*_trips_today`); placement = new `apps/analytics`, snapshots deferred.
Review fixes applied: active_buses & maintenance_due now exclude soft-deleted/retired buses;
driver counts collapsed to one grouped query. Result: 17 analytics tests, 255 total pass.
Branch: feat/p6-admin-kpis
Created: 2026-06-11 (zero AUTO → plan)
Endpoint: `GET /api/v1/admin/overview/kpis/` (admin-only)

Derived from a 12-agent understand→design→judge→synthesize workflow
(run wf_be98d72a-4ea). Judge aggregate: **A=42 > B=37 > C=36**.

## Chosen approach — A (analytics-no-model), with grafts from B/C
New dedicated app `apps/analytics/` holding ONLY a versioned read/aggregation layer
(v1 view + output serializer + `KpiService` + one cross-cutting `AnalyticsRepository`).
**No model, no migration** in this slice — aggregates LIVE across the six existing apps.
This is the documented P6 home for `analytics_snapshots` + the Recharts endpoints, so the
concern lands in the right place with a purely additive P6 path.

Grafts: (1) compute a REAL `avg_delay` from `Trip.end_time − start_time` vs
`Route.estimated_duration` (not a 0.0 stub); (2) explicit empty-DB-zeros + `avg_delay=None`
when no data; (3) full fleet/trip status histograms from single grouped queries;
(4) keep ALL aggregation ORM in one auditable `AnalyticsRepository` (not spread across 5 apps).

Rejected: B's `analytics_snapshots` model/migration/Celery scaffold = premature (nothing
reads it yet). C's extend-trips = turns trips into a 5-app hub (worst coupling).

## KPI fields (verified against real models)
Counts (IntegerField): `active_buses` (distinct buses on IN_PROGRESS trips),
`total_buses`, `buses_active`, `buses_idle`, `buses_in_maintenance`, `buses_retired`,
`scheduled_trips`, `active_trips`, `completed_trips`, `cancelled_trips`,
`passengers_today` (tickets created today), `open_alerts` (SOS driver-logs today),
`maintenance_due` (distinct buses w/ `next_due <= today`), `total_routes`,
`total_drivers`, `verified_drivers`.
Money: `revenue` (DecimalField → string "0.00"; `Payment.status=SUCCESS` today, `Sum` w/ Coalesce).
Float|null: `avg_delay` (minutes, 1dp, null when no completed trips today).

## Layering (View → Service → Repository, ORM only in repository)
- **AnalyticsRepository** (`apps/analytics/repository/AnalyticsRepository.py`): the single
  cross-cutting aggregation repo. All `Count/Sum/values/annotate/distinct` live here.
  Imports domain MODELS + ENUMS (TripStatus, BusStatus, PaymentStatus, DriverLogEventType,
  User.Roles) directly — one-way dep, no cycle. Portable across sqlite(test)/Postgres(prod):
  no `.distinct(field)`, no DB epoch extraction.
  - `completed_trips_with_duration()` annotates RAW `DurationField` only; minute math + baseline
    subtraction + averaging done in Python in the service (portability).
  - `driver_count`/`verified_driver_count` MUST filter `is_deleted=False` explicitly
    (UserManager does NOT hide soft-deleted — verified).
- **KpiService** (`v1/service/KpiService.py`): `@staticmethod` only, ZERO ORM. `overview()`
  orchestrates repo calls, owns `_today_window()` (`timezone.localtime`, half-open [start,now)),
  `_q()` Decimal quantize (WalletService invariant), `_avg_delay_minutes()`. Returns a flat dict.
- **KpiSerializer** (`v1/serializers/KpiSerializer.py`): plain `serializers.Serializer`
  (no model). Typed output fields for OpenAPI; revenue as DecimalField (string), avg_delay
  FloatField(allow_null=True).
- **KpiOverviewView** (`v1/views/KpiViews.py`): `APIView`, `permission_classes=[IsAdmin]`,
  `@extend_schema(tags=["admin-analytics"], responses=KpiSerializer)`, returns
  `CustomResponse(KpiSerializer(KpiService.overview()).data)`. Mirrors FleetSnapshotView.

## Files
CREATE: `apps/analytics/{__init__,apps,urls}.py`, `v1/{__init__,urls}.py`,
`v1/views/{__init__,KpiViews}.py`, `v1/serializers/{__init__,KpiSerializer}.py`,
`v1/service/{__init__,KpiService}.py`, `repository/{__init__,AnalyticsRepository}.py`,
`tests/{__init__,test_kpis_api}.py`.
MODIFY: `config/settings/base.py` (add `"apps.analytics"` after maintenance, INSTALLED_APPS),
`config/urls.py` (add `path("api/", include("apps.analytics.urls"))` after maintenance).
Migrations: NONE (verify via `makemigrations --check --dry-run` → "No changes detected").

## Test plan (mirror apps/maintenance/tests/test_maintenance_api.py)
Inline fixtures (client/admin/passenger/driver via `User.objects.create_user`), plain ORM
seeds, `resp.json()["data"]` envelope assertions. Cases: RBAC 401/403/200; envelope shape
(data dict, meta None); all field keys present; empty-DB zeros + revenue "0.00" + avg_delay
None; active_buses distinct (2 trips/1 bus → 1); fleet histogram; passengers_today + revenue
"35.00"; revenue excludes FAILED/REFUNDED; today-window boundary (backdate via all_objects);
avg_delay real (45min run − 30 baseline → 15.0, proves DurationField on sqlite); avg_delay
None; maintenance_due distinct; open_alerts (SOS today only); driver counts ignore
soft-deleted; soft-deleted bus drops from histogram.

## Verification (from backend/, venv)
`ruff check apps/analytics config/urls.py config/settings/base.py` · `ruff format --check apps/analytics`
· `python manage.py check` · `python manage.py makemigrations --check --dry-run` (No changes)
· `python manage.py spectacular --validate --fail-on-warn` · `pytest apps/analytics/tests -q`
· full `pytest -q` (238 + new stay green).

## Open decisions (pending — see AskUserQuestion)
1. **KPI breadth**: rich ~18-field set (recommended, matches frontend needs) vs spec's 4
   (active_buses, passengers_today, avg_delay, revenue).
2. **Trip status counts**: LIFETIME (default) vs TODAY-scoped.
3. **App placement**: new `apps/analytics` + defer snapshots (recommended) vs extend trips
   vs scaffold `analytics_snapshots` now.
Assumed defaults (reasonable, stated): `today` = admin local day (`timezone.localtime`);
`active_buses` = distinct buses on in-progress trips (we also expose `buses_active` fleet
status to de-risk); `avg_delay` = derived (run − route.estimated_duration, floored, averaged).

## Out of scope (later P6/P5)
analytics_snapshots model + Celery rollups; the 10 Recharts/time-series endpoints; exports;
WS feeds (/ws/fleet, /ws/alerts); /admin/alerts, /admin/anomalies, AI route-suggestions;
frontend admin overview page + api client module.
