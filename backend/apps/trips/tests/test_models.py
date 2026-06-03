"""Model-level tests: trip defaults, soft delete, GPS ordering, and PROTECT guards."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone

from apps.buses.models import Bus, Route
from apps.trips.enums import TripStatus
from apps.trips.models import GpsLocation, Trip
from apps.trips.repository import GpsLocationRepository

User = get_user_model()


@pytest.fixture
def route(db) -> Route:
    return Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)


@pytest.fixture
def driver(db) -> User:
    return User.objects.create_user(
        email="driver@smart-transit.ai", password="Demo1234!", role="driver"
    )


@pytest.fixture
def bus(db) -> Bus:
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


@pytest.fixture
def trip(route, driver, bus) -> Trip:
    return Trip.objects.create(bus=bus, route=route, driver=driver)


@pytest.mark.django_db
def test_trip_defaults_to_scheduled(trip):
    assert trip.status == TripStatus.SCHEDULED
    assert trip.start_time is None
    assert trip.end_time is None
    assert trip.passenger_count is None


@pytest.mark.django_db
def test_soft_delete_hides_from_default_manager(trip):
    trip.delete()  # soft delete

    assert not Trip.objects.filter(pk=trip.pk).exists()  # hidden from default
    tombstone = Trip.all_objects.get(pk=trip.pk)  # still present via escape hatch
    assert tombstone.is_deleted is True


@pytest.mark.django_db
def test_gps_bulk_create_and_latest_ordering(trip):
    base = datetime(2026, 6, 3, 8, 0, 0, tzinfo=UTC)
    rows = [
        GpsLocation(
            trip=trip,
            lat=Decimal("27.700000"),
            lng=Decimal("85.300000"),
            speed=Decimal("12.50"),
            timestamp=base + timedelta(minutes=offset),
        )
        for offset in (0, 5, 10)
    ]
    GpsLocationRepository.bulk_insert(rows)

    assert GpsLocation.objects.filter(trip=trip).count() == 3
    latest = GpsLocationRepository.latest_for_trip(trip.pk)
    assert latest.timestamp == base + timedelta(minutes=10)


@pytest.mark.django_db
def test_latest_for_trips_returns_newest_per_trip(route, driver, bus):
    base = timezone.now()
    t1 = Trip.objects.create(bus=bus, route=route, driver=driver)
    t2 = Trip.objects.create(bus=bus, route=route, driver=driver)
    for t in (t1, t2):
        GpsLocationRepository.bulk_insert(
            [
                GpsLocation(
                    trip=t,
                    lat=Decimal("27.700000"),
                    lng=Decimal("85.300000"),
                    speed=Decimal("12.50"),
                    timestamp=base + timedelta(minutes=offset),
                )
                for offset in (0, 5, 10)
            ]
        )

    latest = list(GpsLocationRepository.latest_for_trips([t1.id, t2.id]))

    assert len(latest) == 2
    by_trip = {row.trip_id: row for row in latest}
    assert by_trip[t1.id].timestamp == base + timedelta(minutes=10)
    assert by_trip[t2.id].timestamp == base + timedelta(minutes=10)


@pytest.mark.django_db
def test_gps_cascades_when_trip_hard_deleted(trip):
    GpsLocation.objects.create(
        trip=trip,
        lat=Decimal("27.700000"),
        lng=Decimal("85.300000"),
        speed=Decimal("0.00"),
        timestamp=datetime(2026, 6, 3, 8, 0, 0, tzinfo=UTC),
    )
    trip.hard_delete()
    assert GpsLocation.objects.count() == 0


@pytest.mark.django_db
def test_referenced_bus_is_protected(trip):
    with pytest.raises(models.ProtectedError), transaction.atomic():
        trip.bus.hard_delete()


@pytest.mark.django_db
def test_referenced_route_is_protected(trip):
    with pytest.raises(models.ProtectedError), transaction.atomic():
        trip.route.hard_delete()


@pytest.mark.django_db
def test_referenced_driver_is_protected(trip):
    # User.delete() is a soft delete; a queryset delete hits the DB-level PROTECT.
    with pytest.raises(models.ProtectedError), transaction.atomic():
        User.objects.filter(pk=trip.driver.pk).delete()
