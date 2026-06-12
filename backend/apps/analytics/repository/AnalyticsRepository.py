"""AnalyticsRepository — the single cross-cutting aggregation data-access layer.

Analytics is inherently cross-domain, so this ONE repository deliberately spans many
models instead of following the per-model ``BaseRepository`` idiom: it concentrates ALL
aggregation ORM (``Count``/``Sum``/``values``/``annotate``/``distinct``) in one auditable,
one-directional file (analytics → domain apps, never the reverse — no import cycle). It
imports domain MODELS + ENUMS directly (not the per-app repositories, which force
``select_related`` row-shaping that is wasteful for a pure ``COUNT``/``SUM`` and expose no
aggregates). Keeping the ORM here lets ``KpiService`` stay ORM-free.

All queries are portable across SQLite (tests) and PostgreSQL (prod): no ``.distinct(field)``
and no DB-specific epoch extraction. ``completed_trips_with_duration`` annotates only the raw
``DurationField`` interval; the minute math + averaging happen in Python in the service.

Soft delete: every non-``User`` model uses ``SoftDeleteManager`` (``.objects`` already hides
``is_deleted`` rows). ``User`` does NOT — ``UserManager`` is a plain ``BaseUserManager`` with no
``get_queryset`` override — so driver counts filter ``is_deleted=False`` explicitly.
"""

from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import User
from apps.buses.enums import BusStatus
from apps.buses.models import Bus, Route
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.models import DriverLog
from apps.maintenance.models import MaintenanceLog
from apps.payments.enums import PaymentStatus
from apps.payments.models import Payment, Ticket
from apps.trips.enums import TripStatus
from apps.trips.models import Trip

_REVENUE_OUTPUT = DecimalField(max_digits=12, decimal_places=2)


class AnalyticsRepository:
    # ── Fleet ────────────────────────────────────────────────────────────────
    @classmethod
    def active_bus_count(cls) -> int:
        """Distinct (non-deleted) buses currently on an IN_PROGRESS trip (FleetSnapshot semantics).

        ``bus__is_deleted=False`` keeps this consistent with ``bus_status_counts``: a bus
        soft-deleted while it still has an in-progress trip must not inflate active_buses.
        """
        return (
            Trip.objects.filter(status=TripStatus.IN_PROGRESS, bus__is_deleted=False)
            .values("bus_id")
            .distinct()
            .count()
        )

    @classmethod
    def bus_status_counts(cls) -> dict[str, int]:
        """``{status: n}`` over the fleet — one grouped query powers total + per-status."""
        return {
            row["status"]: row["n"] for row in Bus.objects.values("status").annotate(n=Count("id"))
        }

    # ── Trips ────────────────────────────────────────────────────────────────
    @classmethod
    def trip_status_counts(cls) -> dict[str, int]:
        """Lifetime ``{status: n}`` over all trips."""
        return {
            row["status"]: row["n"] for row in Trip.objects.values("status").annotate(n=Count("id"))
        }

    @classmethod
    def trip_status_counts_today(cls, start, end) -> dict[str, int]:
        """``{status: n}`` over trips created in the half-open ``[start, end)`` window."""
        return {
            row["status"]: row["n"]
            for row in (
                Trip.objects.filter(created_at__gte=start, created_at__lt=end)
                .values("status")
                .annotate(n=Count("id"))
            )
        }

    @classmethod
    def completed_trips_with_duration(cls, start, end):
        """Raw run-duration rows for today's completed trips.

        Returns ``{"run": timedelta, "route__estimated_duration": minutes}`` per trip. The
        repo annotates only the ``end_time - start_time`` interval (a portable
        ``DurationField``); the service converts to minutes and averages in Python.
        """
        return (
            Trip.objects.filter(
                status=TripStatus.COMPLETED,
                end_time__gte=start,
                end_time__lt=end,
                start_time__isnull=False,
                end_time__isnull=False,
            )
            .annotate(
                run=ExpressionWrapper(F("end_time") - F("start_time"), output_field=DurationField())
            )
            .select_related("route")
            .values("run", "route__estimated_duration")
        )

    # ── Tickets / revenue ──────────────────────────────────────────────────────
    @classmethod
    def tickets_issued_count(cls, start, end) -> int:
        """Tickets created in ``[start, end)`` — today's ridership proxy."""
        return Ticket.objects.filter(created_at__gte=start, created_at__lt=end).count()

    @classmethod
    def revenue_success_sum(cls, start, end) -> Decimal:
        """Sum of SUCCESS payments in ``[start, end)``; ``Decimal('0.00')`` on empty set."""
        return Payment.objects.filter(
            status=PaymentStatus.SUCCESS,
            created_at__gte=start,
            created_at__lt=end,
        ).aggregate(
            total=Coalesce(Sum("amount"), Value(Decimal("0.00")), output_field=_REVENUE_OUTPUT)
        )["total"]

    # ── Operations ──────────────────────────────────────────────────────────────
    @classmethod
    def open_sos_count(cls, start, end) -> int:
        """SOS driver-logs whose event time falls in ``[start, end)``."""
        return DriverLog.objects.filter(
            event_type=DriverLogEventType.SOS,
            timestamp__gte=start,
            timestamp__lt=end,
        ).count()

    @classmethod
    def buses_maintenance_due_count(cls) -> int:
        """Distinct in-service buses with a passed ``next_due`` (the MAINTENANCE_DUE signal).

        Excludes soft-deleted and RETIRED buses — a vehicle out of the active fleet is not
        actionably "due for service" and must not contradict the fleet histogram.
        """
        return (
            MaintenanceLog.objects.filter(
                next_due__isnull=False,
                next_due__lte=timezone.localdate(),
                bus__is_deleted=False,
            )
            .exclude(bus__status=BusStatus.RETIRED)
            .values("bus_id")
            .distinct()
            .count()
        )

    # ── Reference totals ──────────────────────────────────────────────────────
    @classmethod
    def route_count(cls) -> int:
        return Route.objects.count()

    @classmethod
    def driver_counts(cls) -> dict[str, int]:
        """``{"total", "verified"}`` active drivers in ONE grouped query (file idiom).

        Explicit ``is_deleted=False``: UserManager does NOT hide soft-deleted rows.
        """
        return User.objects.filter(role=User.Roles.DRIVER, is_deleted=False).aggregate(
            total=Count("id"),
            verified=Count("id", filter=Q(is_verified=True)),
        )
