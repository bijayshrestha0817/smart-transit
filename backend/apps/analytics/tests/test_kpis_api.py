"""Admin KPI overview — RBAC, envelope shape, and per-KPI aggregation correctness.

Role auth uses ``client.force_authenticate(user=...)`` (DRF supports it even with the
cookie-JWT default). Body assertions read the rendered ``{data, meta, errors}`` envelope.
Seeds use plain ORM creates (no factory_boy) on the test SQLite DB.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.buses.enums import BusStatus
from apps.buses.models import Bus, Route
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.models import DriverLog
from apps.maintenance.models import MaintenanceLog
from apps.payments.enums import PaymentGateway, PaymentStatus
from apps.payments.models import Payment, Ticket
from apps.trips.enums import TripStatus
from apps.trips.models import Trip

User = get_user_model()

KPIS_URL = "/api/v1/admin/overview/kpis/"
PASSWORD = "StrongPass123!"

KPI_KEYS = {
    "active_buses",
    "total_buses",
    "buses_active",
    "buses_idle",
    "buses_in_maintenance",
    "buses_retired",
    "scheduled_trips",
    "active_trips",
    "completed_trips",
    "cancelled_trips",
    "scheduled_trips_today",
    "active_trips_today",
    "completed_trips_today",
    "cancelled_trips_today",
    "passengers_today",
    "revenue",
    "avg_delay",
    "open_alerts",
    "maintenance_due",
    "total_routes",
    "total_drivers",
    "verified_drivers",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        email="admin@example.com", password=PASSWORD, role=User.Roles.ADMIN, is_verified=True
    )


@pytest.fixture
def passenger(db):
    return User.objects.create_user(email="rider@example.com", password=PASSWORD, is_verified=True)


@pytest.fixture
def driver(db):
    return User.objects.create_user(
        email="driver@example.com", password=PASSWORD, role=User.Roles.DRIVER, is_verified=True
    )


# ── Seed helpers ─────────────────────────────────────────────────────────────
def _route() -> Route:
    return Route.objects.create(
        name="R1", estimated_duration=30, color="#1E88E5", fare=Decimal("35.00")
    )


def _bus(plate: str, status: str = BusStatus.IDLE) -> Bus:
    return Bus.objects.create(plate=plate, capacity=40, status=status)


def _driver(email: str, *, is_verified: bool = False) -> User:
    return User.objects.create_user(
        email=email, password=PASSWORD, role=User.Roles.DRIVER, is_verified=is_verified
    )


def _trip(bus, route, drv, status, *, start_time=None, end_time=None) -> Trip:
    return Trip.objects.create(
        bus=bus, route=route, driver=drv, status=status, start_time=start_time, end_time=end_time
    )


def _ticket(passenger_user, trip) -> Ticket:
    return Ticket.objects.create(passenger=passenger_user, trip=trip, fare=Decimal("35.00"))


def _payment(ticket, amount: str, status: str, txn_ref: str) -> Payment:
    return Payment.objects.create(
        ticket=ticket,
        amount=Decimal(amount),
        gateway=PaymentGateway.WALLET,
        status=status,
        txn_ref=txn_ref,
    )


# ── RBAC ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_requires_auth(client):
    assert client.get(KPIS_URL).status_code == 401


@pytest.mark.django_db
def test_passenger_forbidden(client, passenger):
    client.force_authenticate(user=passenger)
    assert client.get(KPIS_URL).status_code == 403


@pytest.mark.django_db
def test_driver_forbidden(client, driver):
    client.force_authenticate(user=driver)
    assert client.get(KPIS_URL).status_code == 403


# ── Envelope + empty DB ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_envelope_shape_and_empty_zeros(client, admin):
    client.force_authenticate(user=admin)
    resp = client.get(KPIS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], dict)
    assert body["meta"] is None
    assert body["errors"] is None

    data = body["data"]
    assert set(data) == KPI_KEYS  # every field present, nothing extra
    # Empty DB: all counts zero, revenue the string "0.00", avg_delay null.
    assert data["active_buses"] == 0
    assert data["total_buses"] == 0
    assert data["active_trips"] == 0
    assert data["passengers_today"] == 0
    assert data["revenue"] == "0.00"
    assert data["avg_delay"] is None
    assert data["open_alerts"] == 0
    assert data["maintenance_due"] == 0
    assert data["total_drivers"] == 0


# ── Fleet / trip aggregation ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_active_buses_distinct_and_trip_counts(client, admin):
    route = _route()
    bus = _bus("BA 1 KHA 1001", status=BusStatus.ACTIVE)
    drv = _driver("d-trips@example.com")
    # Two IN_PROGRESS trips on the SAME bus + one COMPLETED on another bus.
    _trip(bus, route, drv, TripStatus.IN_PROGRESS)
    _trip(bus, route, drv, TripStatus.IN_PROGRESS)
    _trip(_bus("BA 1 KHA 1002"), route, drv, TripStatus.COMPLETED)

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["active_buses"] == 1  # distinct bus, not 2 trips
    assert data["active_trips"] == 2
    assert data["completed_trips"] == 1


@pytest.mark.django_db
def test_active_buses_excludes_soft_deleted_bus(client, admin):
    route = _route()
    drv = _driver("d-del@example.com")
    bus = _bus("BA 1 DEL 1", status=BusStatus.ACTIVE)
    _trip(bus, route, drv, TripStatus.IN_PROGRESS)
    bus.delete()  # soft-delete a bus that still has an in-progress trip

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["active_buses"] == 0  # not counted — consistent with total_buses
    assert data["total_buses"] == 0


@pytest.mark.django_db
def test_fleet_status_histogram(client, admin):
    _bus("BA 1 PA 1", status=BusStatus.ACTIVE)
    _bus("BA 1 PA 2", status=BusStatus.IDLE)
    _bus("BA 1 PA 3", status=BusStatus.MAINTENANCE)

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["buses_active"] == 1
    assert data["buses_idle"] == 1
    assert data["buses_in_maintenance"] == 1
    assert data["buses_retired"] == 0
    assert data["total_buses"] == 3


@pytest.mark.django_db
def test_soft_deleted_bus_drops_from_histogram(client, admin):
    bus = _bus("BA 1 SOFT 1", status=BusStatus.ACTIVE)
    client.force_authenticate(user=admin)
    assert client.get(KPIS_URL).json()["data"]["total_buses"] == 1
    bus.delete()  # soft delete
    assert client.get(KPIS_URL).json()["data"]["total_buses"] == 0


# ── Ridership + revenue ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_passengers_today_and_revenue(client, admin, passenger):
    route = _route()
    drv = _driver("d-rev@example.com")
    trip = _trip(_bus("BA 1 REV 1"), route, drv, TripStatus.IN_PROGRESS)
    ticket = _ticket(passenger, trip)
    _payment(ticket, "35.00", PaymentStatus.SUCCESS, "txn-success-1")

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["passengers_today"] == 1
    assert data["revenue"] == "35.00"  # Decimal serialized AS STRING


@pytest.mark.django_db
def test_revenue_excludes_non_success(client, admin, passenger):
    route = _route()
    drv = _driver("d-rev2@example.com")
    trip = _trip(_bus("BA 1 REV 2"), route, drv, TripStatus.IN_PROGRESS)
    _payment(_ticket(passenger, trip), "35.00", PaymentStatus.SUCCESS, "txn-ok")
    _payment(_ticket(passenger, trip), "99.00", PaymentStatus.FAILED, "txn-fail")
    _payment(_ticket(passenger, trip), "50.00", PaymentStatus.REFUNDED, "txn-refund")

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["revenue"] == "35.00"  # only the SUCCESS payment counts


@pytest.mark.django_db
def test_today_window_excludes_yesterday(client, admin, passenger):
    route = _route()
    drv = _driver("d-win@example.com")
    trip = _trip(_bus("BA 1 WIN 1"), route, drv, TripStatus.IN_PROGRESS)
    ticket = _ticket(passenger, trip)
    payment = _payment(ticket, "35.00", PaymentStatus.SUCCESS, "txn-win")
    # Backdate to yesterday — .update() bypasses auto_now_add.
    yesterday = timezone.now() - timedelta(days=1)
    Ticket.objects.filter(pk=ticket.pk).update(created_at=yesterday)
    Payment.objects.filter(pk=payment.pk).update(created_at=yesterday)

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["passengers_today"] == 0
    assert data["revenue"] == "0.00"


# ── avg_delay (derived metric) ────────────────────────────────────────────────
@pytest.mark.django_db
def test_avg_delay_real_computation(client, admin):
    route = _route()  # estimated_duration = 30 min
    drv = _driver("d-delay@example.com")
    end = timezone.now() - timedelta(minutes=1)
    start = end - timedelta(minutes=45)  # ran 45 min vs 30 baseline -> 15 min late
    _trip(_bus("BA 1 DLY 1"), route, drv, TripStatus.COMPLETED, start_time=start, end_time=end)

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["avg_delay"] == 15.0  # also proves DurationField annotation runs on sqlite


@pytest.mark.django_db
def test_avg_delay_none_without_completed_trips(client, admin):
    client.force_authenticate(user=admin)
    assert client.get(KPIS_URL).json()["data"]["avg_delay"] is None


# ── Operations: maintenance due + alerts ──────────────────────────────────────
@pytest.mark.django_db
def test_maintenance_due_distinct_buses(client, admin):
    bus = _bus("BA 1 MNT 1")
    now = timezone.now()
    past = timezone.localdate() - timedelta(days=1)
    future = timezone.localdate() + timedelta(days=30)
    # Two overdue logs on the SAME bus -> counts once.
    MaintenanceLog.objects.create(
        bus=bus, service_type="Oil", cost=Decimal("100.00"), serviced_at=now, next_due=past
    )
    MaintenanceLog.objects.create(
        bus=bus, service_type="Brakes", cost=Decimal("200.00"), serviced_at=now, next_due=past
    )
    # A different bus due only in the future -> not counted.
    MaintenanceLog.objects.create(
        bus=_bus("BA 1 MNT 2"),
        service_type="Tyres",
        cost=Decimal("300.00"),
        serviced_at=now,
        next_due=future,
    )

    client.force_authenticate(user=admin)
    assert client.get(KPIS_URL).json()["data"]["maintenance_due"] == 1


@pytest.mark.django_db
def test_maintenance_due_excludes_retired_and_deleted_buses(client, admin):
    now = timezone.now()
    past = timezone.localdate() - timedelta(days=1)
    retired = _bus("BA 1 RET 1", status=BusStatus.RETIRED)
    deleted = _bus("BA 1 RET 2", status=BusStatus.ACTIVE)
    for bus in (retired, deleted):
        MaintenanceLog.objects.create(
            bus=bus, service_type="Oil", cost=Decimal("100.00"), serviced_at=now, next_due=past
        )
    deleted.delete()  # soft-delete

    client.force_authenticate(user=admin)
    # Both overdue buses are out of the active fleet -> neither counts.
    assert client.get(KPIS_URL).json()["data"]["maintenance_due"] == 0


@pytest.mark.django_db
def test_open_alerts_sos_today_only(client, admin):
    drv = _driver("d-sos@example.com")
    now = timezone.now()
    DriverLog.objects.create(driver=drv, event_type=DriverLogEventType.SOS, timestamp=now)
    # A non-SOS event today and an SOS dated yesterday -> neither counted.
    DriverLog.objects.create(driver=drv, event_type=DriverLogEventType.NOTE, timestamp=now)
    DriverLog.objects.create(
        driver=drv, event_type=DriverLogEventType.SOS, timestamp=now - timedelta(days=1)
    )

    client.force_authenticate(user=admin)
    assert client.get(KPIS_URL).json()["data"]["open_alerts"] == 1


# ── Driver counts honor explicit soft-delete filter ───────────────────────────
@pytest.mark.django_db
def test_driver_counts_ignore_soft_deleted(client, admin):
    _driver("active-verified@example.com", is_verified=True)
    d2 = _driver("active-unverified@example.com", is_verified=False)

    client.force_authenticate(user=admin)
    data = client.get(KPIS_URL).json()["data"]
    assert data["total_drivers"] == 2
    assert data["verified_drivers"] == 1

    d2.delete()  # soft delete
    data = client.get(KPIS_URL).json()["data"]
    assert data["total_drivers"] == 1
    assert data["verified_drivers"] == 1
