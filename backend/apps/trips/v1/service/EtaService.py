"""Baseline ETA heuristic — the P5 "graceful fallback" before the ML model lands.

Pure and ORM-free: callers (``TripService``) pass the trip, its latest GPS breadcrumb,
and the route's ordered stops; this returns a small dict the serializer renders. It never
raises and never hits the DB, so it is cheap to call per-trip in the fleet/active loops and
trivially unit-testable.

Strategy (in priority order):
1. Trip not IN_PROGRESS                      -> ``unavailable``.
2. Usable GPS fix + at least one stop ahead  -> ``gps``: straight-line distance to the next
   stop divided by a speed estimate (live speed, else route-average, else a city default).
3. Trip started + route has a baseline duration -> ``schedule``: time left on the timetable.
4. Nothing computable                        -> ``unavailable``.

Straight-line (haversine) distance under-counts road distance, so the GPS estimate is
mildly optimistic — acceptable for a baseline and documented in the plan. ``speed`` is in
km/h (the GPS ``DecimalField`` convention used by the seed and tests).
"""

from apps.common.geo import haversine_km
from apps.trips.enums import TripStatus

MIN_SPEED_KMH = 5.0  # below this, a "live" speed is treated as stopped/noise -> use averages
DEFAULT_SPEED_KMH = 18.0  # city-bus fallback when no live or route-average speed is available

_UNAVAILABLE = {"minutes": None, "seconds": None, "next_stop": None, "source": "unavailable"}


class EtaService:
    @staticmethod
    def estimate(trip, last_position, stops) -> dict:
        """Estimate arrival at the next stop. See module docstring for the strategy.

        ``stops`` is an ordered iterable of BusStop (by ``sequence``); ``last_position`` is
        the latest GpsLocation or ``None``.
        """
        if trip is None or trip.status != TripStatus.IN_PROGRESS:
            return dict(_UNAVAILABLE)

        ordered = sorted(stops, key=lambda s: s.sequence) if stops else []

        gps = EtaService._gps_estimate(trip, last_position, ordered)
        if gps is not None:
            return gps

        schedule = EtaService._schedule_estimate(trip)
        if schedule is not None:
            return schedule

        return dict(_UNAVAILABLE)

    # ── GPS path ──────────────────────────────────────────────────────────────
    @staticmethod
    def _gps_estimate(trip, last_position, ordered_stops) -> dict | None:
        if last_position is None or not ordered_stops:
            return None
        cur_lat, cur_lng = last_position.lat, last_position.lng
        if cur_lat is None or cur_lng is None:
            return None

        next_stop = EtaService._next_stop(cur_lat, cur_lng, ordered_stops)
        if next_stop is None:
            return None

        remaining_km = haversine_km(cur_lat, cur_lng, next_stop.lat, next_stop.lng)
        speed_kmh = EtaService._speed_kmh(last_position, trip, ordered_stops)
        if speed_kmh <= 0:
            return None

        seconds = max(0, round(remaining_km / speed_kmh * 3600))
        return {
            "minutes": round(seconds / 60),
            "seconds": seconds,
            "next_stop": next_stop.name,
            "source": "gps",
        }

    @staticmethod
    def _next_stop(cur_lat, cur_lng, ordered_stops):
        """The stop the bus is heading toward: the one after the nearest stop by sequence.

        If the nearest stop is the terminus, that terminus IS the target (arriving). Falls
        back to the nearest stop itself when no later stop exists.
        """
        nearest = min(
            ordered_stops,
            key=lambda s: haversine_km(cur_lat, cur_lng, s.lat, s.lng),
        )
        ahead = [s for s in ordered_stops if s.sequence > nearest.sequence]
        return ahead[0] if ahead else nearest

    @staticmethod
    def _speed_kmh(last_position, trip, ordered_stops) -> float:
        """Live speed if it's above the noise floor, else route-average, else a city default."""
        live = last_position.speed
        if live is not None and float(live) >= MIN_SPEED_KMH:
            return float(live)

        avg = EtaService._route_average_speed(trip, ordered_stops)
        return avg if avg and avg > 0 else DEFAULT_SPEED_KMH

    @staticmethod
    def _route_average_speed(trip, ordered_stops) -> float | None:
        """route length (sum of stop-to-stop legs) / baseline duration → km/h, or None."""
        duration_min = getattr(trip.route, "estimated_duration", None)
        if not duration_min or len(ordered_stops) < 2:
            return None
        total_km = sum(
            haversine_km(a.lat, a.lng, b.lat, b.lng)
            for a, b in zip(ordered_stops, ordered_stops[1:], strict=False)
        )
        if total_km <= 0:
            return None
        return total_km / (duration_min / 60.0)

    # ── Schedule fallback ───────────────────────────────────────────────────────
    @staticmethod
    def _schedule_estimate(trip) -> dict | None:
        from django.utils import timezone

        duration_min = getattr(trip.route, "estimated_duration", None)
        if not trip.start_time or not duration_min:
            return None
        elapsed = (timezone.now() - trip.start_time).total_seconds()
        seconds = max(0, round(duration_min * 60 - elapsed))
        return {
            "minutes": round(seconds / 60),
            "seconds": seconds,
            "next_stop": None,
            "source": "schedule",
        }
