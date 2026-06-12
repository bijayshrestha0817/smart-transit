# Project Timeline (maintained by zero)

<!-- Newest entries at the bottom. Commits seeded from git log; sessions appended. -->

## 2026-06-02 — c703e56
- chore(claude): align ported skills to this codebase + add project hooks.

## 2026-06-03 — ee971c1
- refactor(backend): layered View→Service→Repository with v1 packages. Establishes the
  core architecture.

## 2026-06-03 — 2cb8547
- refactor(backend): align layout to reference (service/ singular, app url dispatch,
  enums/exceptions, PascalCase).

## 2026-06-03 — ee39ee8
- refactor(docs): update GOTCHAS and SKILL docs for PascalCase conventions + domain
  exceptions.

## 2026-06-03 — 60a325e
- feat(frontend): scaffold P0 Next.js 16 shell with cookie-JWT auth.

## 2026-06-03 — c7c7efb / b11396a (PR #1)
- Add initial backend documentation; merge `refactor/layered-v1-architecture`. **P0 backend
  foundation + auth landed.**

## 2026-06-03 — 01ddbc9 / dd480c7 / ca2ded0 (PR #2)
- feat: UI components and hooks; ci: gate the frontend (lint + Next build); merge
  `feat/p1-frontend`. **P1 frontend + domain CRUD.**

## 2026-06-04 — a878dac
- feat: hooks for cursor pagination, geolocation, WebSocket management (P2/P3 frontend
  groundwork).

## 2026-06-04 — ff2f15d
- feat: notifications system with trip-completion alerts (notifications app + realtime push).

## 2026-06-04 — 652f07f
- feat: ticket management features for passengers (P4 frontend).

## 2026-06-05 — e05081a
- feat: maintenance log CRUD + notifications (maintenance app).

## 2026-06-05 — e3d1217 (PR #3)
- Merge `feat/p4-ticketing-payments`. **P4 ticketing + payments landed.**

## 2026-06-11 — zero session (REVIEW, bootstrap)
- Bootstrapped zero memory (CONTEXT/TIMELINE/STATE). Mapped the codebase: 7 domain apps +
  common base + `realtime/`, layered View→Service→Repository, `{data,meta,errors}` envelope,
  cookie-JWT, soft delete, scoped throttling.
- Reality check: on `main`, clean tree. Created `.venv`, installed dev deps (Django 6.0.6).
- System review: **238 tests passed** (3.70s), ruff check clean, ruff format clean (214
  files), `manage.py check` no issues.
- Phase assessment: P0/P1/P2(backend)/P4 done; P3/P6 frontend partial; **P5 (AI) and P7
  (hardening) not started**. Confirmed gaps: no `/admin/overview/kpis/`, no `/ai|eta`
  endpoints, no health check, empty `CELERY_BEAT_SCHEDULE`, CI on Python 3.12 vs target 3.13.
- Proposed next (ranked): admin KPI/overview endpoint → baseline ETA endpoint →
  health-check endpoint. Awaiting user direction (REVIEW mode).

## 2026-06-11 — zero session (AUTO, P6 admin KPIs)
- Planned `GET /api/v1/admin/overview/kpis/` via a 12-agent understand→design→judge→
  synthesize workflow (judge: new analytics app A=42 > B=37 > C=36). Plan in
  dev/memory/p6-admin-kpis/Planning.md. User chose: rich KPI set, lifetime+today trip
  counts, new app (defer snapshots).
- Implemented new **`apps/analytics`** app on branch `feat/p6-admin-kpis`: layered
  View→Service→Repository, NO model (live aggregation across 6 apps), one cross-cutting
  `AnalyticsRepository` (all aggregation ORM), `KpiService` (@staticmethod, ORM-free,
  today-window + Decimal + Python avg_delay), `KpiSerializer` (output-only, revenue as
  string), `KpiOverviewView` (APIView/IsAdmin/@extend_schema/CustomResponse). Wired
  INSTALLED_APPS + config/urls.py. 22 KPI fields (fleet/trip histograms, today windows,
  revenue, avg_delay, alerts, maintenance_due, driver counts). No migration.
- Self-review (code-review skill, 2 finder agents): fixed 3 findings — active_buses &
  maintenance_due now exclude soft-deleted/retired buses; driver counts collapsed to one
  grouped query. Added 2 edge-case tests.
- Verified: ruff clean, format clean, `manage.py check` clean, makemigrations "No changes",
  spectacular --validate --fail-on-warn clean, **17 analytics tests pass, 255 total pass**.
- Status: implemented + verified, staged, NOT committed (awaiting user to ship).

## 2026-06-11 — zero session (frontend integration, P6 admin KPIs)
- Built the admin KPI dashboard consuming `GET /admin/overview/kpis/`:
  - `src/lib/api/types.ts` (+`AdminKpis`), `src/lib/api/analytics.ts` (`fetchAdminKpis`,
    axios + shared `unwrap`), `src/lib/queryClient.ts` (+`adminKpis` key).
  - `src/components/admin-kpis.tsx` — `<AdminKpis />` (TanStack Query, 60s poll,
    skeleton/error states, headline StatCards + fleet/trips breakdowns + ops strip;
    semantic tones, live ping). Integrated into `(admin)/admin/page.tsx` operator console.
  - `src/components/admin-kpis.test.tsx` — vitest + repo MSW harness (3 tests).
- Verified all four frontend CI gates: ESLint clean, `tsc --noEmit` clean, **vitest 21
  passed** (3 new), **next build** OK (`/admin` in route table).
- Self-review via expert-react agent CONFABULATED a fictional codebase (invented hono
  client, USD formatMoney, TrendChip) — all 6 findings invalid; verified my real code
  against each, all already correct. Lesson recorded to harness memory.
- Both halves staged (backend 17 files + frontend 6 files), NOT committed.
