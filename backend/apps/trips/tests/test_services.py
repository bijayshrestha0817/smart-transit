"""Service-layer tests: trip lifecycle rules, GPS ingest, and the active/fleet shape."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.buses.models import Bus, Route
from apps.trips.enums import TripStatus
from apps.trips.exceptions import (
    TripAlreadyStartedError,
    TripNotAssignedError,
    TripNotInProgressError,
)
from apps.trips.models import GpsLocation, Trip
from apps.trips.v1.service import TripService

User = get_user_model()


@pytest.fixture
def route(db) -> Route:
    return Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)


@pytest.fixture
def bus(db) -> Bus:
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


@pytest.fixture
def driver(db) -> User:
    return User.objects.create_user(
        email="driver@smart-transit.ai", password="Demo1234!", role=User.Roles.DRIVER
    )


@pytest.fixture
def other_driver(db) -> User:
    return User.objects.create_user(
        email="other@smart-transit.ai", password="Demo1234!", role=User.Roles.DRIVER
    )


@pytest.fixture
def trip(route, driver, bus) -> Trip:
    return Trip.objects.create(bus=bus, route=route, driver=driver)


# ── start_trip ───────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_start_trip_happy_path(trip, driver):
    started = TripService.start_trip(trip, driver)
    assert started.status == TripStatus.IN_PROGRESS
    assert started.start_time is not None
    trip.refresh_from_db()
    assert trip.status == TripStatus.IN_PROGRESS


@pytest.mark.django_db
def test_start_trip_already_started_raises_409(trip, driver):
    TripService.start_trip(trip, driver)
    with pytest.raises(TripAlreadyStartedError) as exc:
        TripService.start_trip(trip, driver)
    assert exc.value.status_code == 409


@pytest.mark.django_db
def test_start_trip_wrong_driver_raises_403(trip, other_driver):
    with pytest.raises(TripNotAssignedError) as exc:
        TripService.start_trip(trip, other_driver)
    assert exc.value.status_code == 403


@pytest.mark.django_db
def test_start_completed_trip_raises_409(trip, driver):
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])
    with pytest.raises(TripAlreadyStartedError) as exc:
        TripService.start_trip(trip, driver)
    assert exc.value.status_code == 409


# ── end_trip ─────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_end_trip_happy_path(trip, driver):
    TripService.start_trip(trip, driver)
    ended = TripService.end_trip(trip, driver)
    assert ended.status == TripStatus.COMPLETED
    assert ended.end_time is not None


@pytest.mark.django_db
def test_end_trip_not_in_progress_raises_409(trip, driver):
    with pytest.raises(TripNotInProgressError) as exc:
        TripService.end_trip(trip, driver)
    assert exc.value.status_code == 409


# ── set_passenger_count ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_set_passenger_count(trip, driver):
    updated = TripService.set_passenger_count(trip, driver, 23)
    assert updated.passenger_count == 23
    trip.refresh_from_db()
    assert trip.passenger_count == 23


@pytest.mark.django_db
def test_set_passenger_count_wrong_driver_raises_403(trip, other_driver):
    with pytest.raises(TripNotAssignedError):
        TripService.set_passenger_count(trip, other_driver, 5)


# ── ingest_gps ───────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_ingest_gps_inserts_rows(trip, driver):
    base = timezone.now()
    points = [
        {
            "lat": Decimal("27.700000"),
            "lng": Decimal("85.300000"),
            "speed": Decimal("12.50"),
            "heading": Decimal("90.00"),
            "timestamp": base + timedelta(seconds=offset),
        }
        for offset in (0, 3, 6)
    ]
    count = TripService.ingest_gps(trip, driver, points)
    assert count == 3
    assert GpsLocation.objects.filter(trip=trip).count() == 3
    # Client timestamp is used as-is.
    assert GpsLocation.objects.filter(trip=trip, timestamp=base).exists()


@pytest.mark.django_db
def test_ingest_gps_allows_missing_heading(trip, driver):
    points = [
        {
            "lat": Decimal("27.700000"),
            "lng": Decimal("85.300000"),
            "speed": Decimal("0.00"),
            "timestamp": timezone.now(),
        }
    ]
    assert TripService.ingest_gps(trip, driver, points) == 1
    assert GpsLocation.objects.get(trip=trip).heading is None


@pytest.mark.django_db
def test_ingest_gps_wrong_driver_raises_403(trip, other_driver):
    points = [
        {
            "lat": Decimal("27.700000"),
            "lng": Decimal("85.300000"),
            "speed": Decimal("0.00"),
            "timestamp": timezone.now(),
        }
    ]
    with pytest.raises(TripNotAssignedError) as exc:
        TripService.ingest_gps(trip, other_driver, points)
    assert exc.value.status_code == 403
    assert GpsLocation.objects.filter(trip=trip).count() == 0


# ── active_on_route / fleet_snapshot ─────────────────────────────────────────
def _add_gps(trip, when, lat="27.70", lng="85.30", speed="10.00"):
    return GpsLocation.objects.create(
        trip=trip,
        lat=Decimal(lat),
        lng=Decimal(lng),
        speed=Decimal(speed),
        timestamp=when,
    )


@pytest.mark.django_db
def test_active_on_route_returns_trips_with_latest_position(route, bus, driver):
    base = timezone.now()
    trip = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    _add_gps(trip, base)
    latest = _add_gps(trip, base + timedelta(minutes=5), lat="27.75")
    # A scheduled trip on the same route must be excluded.
    Trip.objects.create(bus=bus, route=route, driver=driver)

    result = TripService.active_on_route(route.id)
    assert len(result) == 1
    assert result[0]["trip"].id == trip.id
    assert result[0]["last_position"].id == latest.id


@pytest.mark.django_db
def test_active_on_route_returns_null_position_when_no_gps(route, bus, driver):
    base = timezone.now()
    Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    result = TripService.active_on_route(route.id)
    assert len(result) == 1
    assert result[0]["last_position"] is None


@pytest.mark.django_db
def test_fleet_snapshot_returns_all_in_progress(route, bus, driver):
    base = timezone.now()
    t1 = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    bus2 = Bus.objects.create(plate="BA 2 KHA 2002", capacity=30)
    t2 = Trip.objects.create(
        bus=bus2, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    _add_gps(t1, base)
    Trip.objects.create(bus=bus, route=route, driver=driver)  # scheduled -> excluded

    snapshot = TripService.fleet_snapshot()
    ids = {row["trip"].id for row in snapshot}
    assert ids == {t1.id, t2.id}
    by_trip = {row["trip"].id: row for row in snapshot}
    assert by_trip[t1.id]["last_position"] is not None
    assert by_trip[t2.id]["last_position"] is None


@pytest.mark.django_db
def test_active_on_route_empty_when_no_in_progress(route, bus, driver):
    # Only a scheduled trip on the route -> nothing active.
    Trip.objects.create(bus=bus, route=route, driver=driver)
    assert TripService.active_on_route(route.id) == []


@pytest.mark.django_db
def test_fleet_snapshot_empty_when_no_in_progress(route, bus, driver):
    Trip.objects.create(bus=bus, route=route, driver=driver)  # scheduled -> excluded
    assert TripService.fleet_snapshot() == []
