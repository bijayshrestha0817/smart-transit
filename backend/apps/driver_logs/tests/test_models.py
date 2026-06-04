"""Model-level tests: driver log defaults, server-stamped timestamp, soft delete, index."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.buses.models import Bus, Route
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.models import DriverLog
from apps.trips.models import Trip

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
        email="driver@smart-transit.ai", password="Demo1234!", role="driver"
    )


@pytest.fixture
def trip(route, driver, bus) -> Trip:
    return Trip.objects.create(bus=bus, route=route, driver=driver)


@pytest.mark.django_db
def test_driver_log_persists_with_defaults(driver):
    before = timezone.now()
    log = DriverLog.objects.create(driver=driver, event_type=DriverLogEventType.NOTE)
    after = timezone.now()
    assert log.id is not None
    assert log.event_type == DriverLogEventType.NOTE
    assert log.notes == ""
    assert log.trip is None
    # timestamp is server-stamped at creation (default=timezone.now).
    assert before <= log.timestamp <= after


@pytest.mark.django_db
def test_driver_log_optional_trip(trip, driver):
    log = DriverLog.objects.create(
        driver=driver, trip=trip, event_type=DriverLogEventType.DELAY, notes="stuck in traffic"
    )
    assert log.trip_id == trip.id
    assert log.notes == "stuck in traffic"


@pytest.mark.django_db
def test_soft_delete_hides_from_default_manager(driver):
    log = DriverLog.objects.create(driver=driver, event_type=DriverLogEventType.FUEL)
    log.delete()  # soft delete
    assert not DriverLog.objects.filter(pk=log.pk).exists()  # hidden from default
    tombstone = DriverLog.all_objects.get(pk=log.pk)  # still present via escape hatch
    assert tombstone.is_deleted is True


@pytest.mark.django_db
def test_trip_set_null_on_hard_delete_keeps_log(trip, driver):
    log = DriverLog.objects.create(driver=driver, trip=trip, event_type=DriverLogEventType.SOS)
    trip.hard_delete()
    log.refresh_from_db()
    assert log.trip_id is None  # SET_NULL — the audit log survives its trip


@pytest.mark.django_db
def test_driver_timestamp_index_present():
    index_fields = {tuple(idx.fields) for idx in DriverLog._meta.indexes}
    assert ("driver", "-timestamp") in index_fields
