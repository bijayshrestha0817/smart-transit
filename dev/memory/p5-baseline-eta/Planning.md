# Plan — P5-lite: Baseline ETA (heuristic) + live integration

Status: DONE — backend + frontend implemented & verified (268 backend / 26 vitest passing); NOT committed
Owner: zero
Branch: `feat/p5-baseline-eta` (stacked on `feat/p6-admin-kpis`, per user — don't ship P6 first)
Created: 2026-06-12

## Goal
Give passengers and operators a live **"arriving in N min"** signal per bus, without the
full ML pipeline. A heuristic ETA service computes time-to-next-stop from the last GPS
breadcrumb + recent speed + route stop geometry, with graceful fallbacks. Surfaced both
in the existing live payloads (`/trips/active/`, `/admin/fleet/`) and a roadmap-named
dedicated endpoint `GET /api/v1/trips/{id}/eta/`.

## Why this slice
- Highest value-for-effort next step; **unblocks P3** (passenger live map ETA display).
- Self-contained, fits the layered View→Service→Repository pattern.
- No ML/training infra needed; the heuristic is the documented P5 "graceful fallback".

## Heuristic (EtaService.estimate)
Pure function, **no ORM** (caller passes trip + last_position + ordered stops). Returns:
```python
{
  "minutes": int | None,          # to next stop (primary); None if unavailable
  "seconds": int | None,
  "next_stop": str | None,        # stop name, or None
  "source": "gps" | "schedule" | "unavailable",
}
```
Algorithm:
1. If trip not IN_PROGRESS → `unavailable`.
2. **GPS path** (last_position present, has lat/lng):
   - Find nearest stop to current position (haversine). Next stop = the stop with
     `sequence > nearest.sequence`; if nearest is terminus → next = terminus (arriving).
   - `remaining_km = haversine(current → next_stop)`.
   - `speed_kmh` = last_position.speed if ≥ `MIN_SPEED_KMH` (5.0); else route avg
     (`route_len_km / (estimated_duration/60)`) if computable; else `DEFAULT_SPEED_KMH` (18).
   - `seconds = remaining_km / speed_kmh * 3600` (guard div-by-zero), clamp ≥ 0.
   - `source="gps"`.
3. **Schedule fallback** (no usable GPS but trip started + estimated_duration):
   - `seconds = max(0, start_time + estimated_duration*60 − now)`; `next_stop=None`;
     `source="schedule"`.
4. **No stops / nothing computable** → `unavailable` (minutes=None). Never raise; never 500.

Constants live at module top in `EtaService.py`.

## Backend changes
| # | File | Change |
|---|------|--------|
| B1 | `apps/common/geo.py` (new) | `haversine_km(lat1,lng1,lat2,lng2) -> float`. Pure, Decimal/float-tolerant. Reusable (BusStopRepository uses a bounding box; this is the true-distance complement). |
| B2 | `apps/trips/v1/service/EtaService.py` (new) | `estimate(trip, last_position, stops) -> dict` per heuristic above. Stateless, ORM-free. |
| B3 | `apps/trips/repository/TripRepository.py` | `in_progress()`/`active()` add `prefetch_related("route__stops")` so eta has stops with no N+1. Add `get_active_with_stops(trip_id)` for the single-trip endpoint. |
| B4 | `apps/trips/v1/service/TripService.py` | `_pair_with_last_position` also computes `eta` per trip (uses prefetched `trip.route.stops`). Add `eta_for_trip(trip_id)` for the dedicated endpoint (fetch trip + latest GPS, call EtaService). |
| B5 | `apps/trips/v1/serializers/TripSerializer.py` | Add `EtaSerializer` (minutes/seconds/next_stop/source). `ActiveTripSerializer` gains nested `eta` (allow_null). |
| B6 | `apps/trips/v1/views/PassengerTripViews.py` | New `TripEtaView(APIView, IsPassenger)` → `GET /trips/{id}/eta/`; 404 if trip not found/not in progress (return `unavailable` eta with 200? → choose: 404 only if no such trip; in-progress check handled by eta source). Returns `CustomResponse(EtaSerializer(...).data)`. |
| B7 | `apps/trips/v1/urls.py` | Wire `trips/<int:pk>/eta/` → `TripEtaView`. |
| B8 | tests | `apps/trips/tests/test_eta_service.py` (unit: gps, terminus, zero-speed guard, schedule fallback, no-stops, completed→unavailable). Extend `test_trip_api.py`: eta present in `/trips/active/` & `/admin/fleet/` payloads; `/trips/{id}/eta/` happy + 404 + RBAC (non-passenger 403). |

Verification: `pytest` green; `ruff check`/`ruff format --check`/`manage.py check`/`makemigrations --check`
(no new migration expected — no model change); `spectacular --validate --fail-on-warn`.

## Frontend changes
ETA delivered via the **REST `ActiveTrip` payload** (both live views already consume
`ActiveTrip[]`). REST refetch (fleet 30s; route on focus/stale) refreshes ETA; WS keeps the
marker moving. WS-pushed ETA is a future (full-P5) enhancement — noted, not built now.

| # | File | Change |
|---|------|--------|
| F1 | `src/lib/api/types.ts` | Add `Eta` interface; `ActiveTrip` gains `eta: Eta \| null`. |
| F2 | `src/lib/format.ts` | `formatEta(eta): string` → "Arriving at {stop} in {n} min" / "Arriving in {n} min" / "Due" (<1 min) / "" when unavailable. |
| F3 | `src/lib/api/trips.ts` | `tripEta(id)` wrapper for `GET /trips/{id}/eta/` (+ `QUERY_KEYS.tripEta`). Light; main integration uses `ActiveTrip.eta`. |
| F4 | `src/components/route-live-section.tsx` | Bus-list row + marker label show `formatEta(at.trip... )` → from `at.eta`. (eta lives on ActiveTrip, not trip.) |
| F5 | `src/app/(admin)/admin/fleet/page.tsx` | Same: side-list row + marker label show ETA. |
| F6 | tests | Extend/borrow the MSW component-test harness (`admin-kpis.test.tsx` style): a `route-live-section` test asserting "Arriving … min" renders from a mocked `eta`. |

Gates: `npm run lint` · `tsc --noEmit` · `vitest` · `next build` — all green.

## Integration contract (the seam)
`ActiveTrip.eta` (nullable). Passenger route view and admin fleet view both read it; no new
fetch wiring. Dedicated `/trips/{id}/eta/` supports future per-trip pages.

## Out of scope (future / full P5)
- ETA pushed over the WS `LocationEvent` (sub-second refresh).
- Polyline-aware distance (uses `route.polyline_json`) instead of straight-line stop hops.
- ML ETA model + `model_version`; occupancy; route optimization; anomaly poll.
- Passenger "my stop" selection → ETA to chosen stop.

## Risks / decisions
- **Straight-line (haversine) underestimates** road distance → ETA optimistic. Acceptable for
  baseline; documented. A constant fudge factor (e.g. ×1.3) is a cheap future tweak.
- **No model change** → no migration. If makemigrations reports changes, stop (blocker).
- Speed in km/h assumed (GPS `speed` DecimalField, max 999.99) — consistent with seed/tests.
