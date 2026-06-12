"""KpiService — assembles the admin overview KPI payload.

A class of ``@staticmethod`` only, with ZERO ORM: it orchestrates ``AnalyticsRepository``
calls, owns the today-window math, quantizes money (the ``WalletService`` invariant), and
converts repo-fetched run durations into an average delay in pure Python (so no DB-specific
epoch extraction is needed — SQLite/PostgreSQL portable). Read-only, so no
``transaction.atomic()``. Returns a flat snake_case dict matching ``KpiSerializer``.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.analytics.repository import AnalyticsRepository
from apps.buses.enums import BusStatus
from apps.trips.enums import TripStatus

TWO_PLACES = Decimal("0.01")


def _q(amount) -> Decimal:
    """Coerce to ``Decimal`` and quantize to 2dp (half-up) — the money invariant."""
    return Decimal(amount or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class KpiService:
    @staticmethod
    def overview() -> dict:
        start, end = KpiService._today_window()
        buses = AnalyticsRepository.bus_status_counts()
        trips = AnalyticsRepository.trip_status_counts()
        trips_today = AnalyticsRepository.trip_status_counts_today(start, end)
        drivers = AnalyticsRepository.driver_counts()
        return {
            # Fleet
            "active_buses": AnalyticsRepository.active_bus_count(),
            "total_buses": sum(buses.values()),
            "buses_active": buses.get(BusStatus.ACTIVE, 0),
            "buses_idle": buses.get(BusStatus.IDLE, 0),
            "buses_in_maintenance": buses.get(BusStatus.MAINTENANCE, 0),
            "buses_retired": buses.get(BusStatus.RETIRED, 0),
            # Trips — lifetime
            "scheduled_trips": trips.get(TripStatus.SCHEDULED, 0),
            "active_trips": trips.get(TripStatus.IN_PROGRESS, 0),
            "completed_trips": trips.get(TripStatus.COMPLETED, 0),
            "cancelled_trips": trips.get(TripStatus.CANCELLED, 0),
            # Trips — today
            "scheduled_trips_today": trips_today.get(TripStatus.SCHEDULED, 0),
            "active_trips_today": trips_today.get(TripStatus.IN_PROGRESS, 0),
            "completed_trips_today": trips_today.get(TripStatus.COMPLETED, 0),
            "cancelled_trips_today": trips_today.get(TripStatus.CANCELLED, 0),
            # Ridership / money / operations (today)
            "passengers_today": AnalyticsRepository.tickets_issued_count(start, end),
            "revenue": _q(AnalyticsRepository.revenue_success_sum(start, end)),
            "avg_delay": KpiService._avg_delay_minutes(
                AnalyticsRepository.completed_trips_with_duration(start, end)
            ),
            "open_alerts": AnalyticsRepository.open_sos_count(start, end),
            "maintenance_due": AnalyticsRepository.buses_maintenance_due_count(),
            # Reference totals
            "total_routes": AnalyticsRepository.route_count(),
            "total_drivers": drivers["total"],
            "verified_drivers": drivers["verified"],
        }

    @staticmethod
    def _today_window():
        """Half-open ``[midnight, now)`` in the admin's local day (USE_TZ=True)."""
        now = timezone.localtime()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now

    @staticmethod
    def _avg_delay_minutes(rows):
        """Average minutes a completed trip ran over its route baseline; ``None`` if none.

        ``rows`` yields ``{"run": timedelta, "route__estimated_duration": int_minutes}``. Per
        trip: ``max(0, run_minutes - baseline)``. Pure Python (no DB epoch math) for portability.
        """
        delays = []
        for row in rows:
            run = row["run"]
            if run is None:
                continue
            run_minutes = run.total_seconds() / 60.0
            baseline = row["route__estimated_duration"] or 0
            delays.append(max(0.0, run_minutes - baseline))
        if not delays:
            return None
        return round(sum(delays) / len(delays), 1)
