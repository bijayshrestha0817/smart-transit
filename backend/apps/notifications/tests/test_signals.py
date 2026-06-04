"""Signal tests: ending a trip produces exactly one TRIP_COMPLETED notification for
the driver (decoupled, idempotent) without ever editing trips code.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.buses.models import Bus, Route
from apps.notifications.enums import NotificationType
from apps.notifications.models import Notification
from apps.trips.enums import TripStatus
from apps.trips.models import Trip
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
        email="driver@example.com", password="Demo1234!", role=User.Roles.DRIVER
    )


@pytest.fixture
def trip(route, driver, bus) -> Trip:
    return Trip.objects.create(bus=bus, route=route, driver=driver)


def _trip_completed(driver):
    return Notification.objects.filter(user=driver, type=NotificationType.TRIP_COMPLETED)


@pytest.mark.django_db
def test_end_trip_creates_one_notification_for_driver(trip, driver):
    TripService.start_trip(trip, driver)
    TripService.end_trip(trip, driver)

    notifications = _trip_completed(driver)
    assert notifications.count() == 1
    notification = notifications.get()
    assert notification.payload_json["trip_id"] == trip.id
    assert notification.payload_json["route_name"] == trip.route.name


@pytest.mark.django_db
def test_resaving_completed_trip_does_not_duplicate(trip, driver):
    TripService.start_trip(trip, driver)
    TripService.end_trip(trip, driver)
    assert _trip_completed(driver).count() == 1

    # Re-save the already-completed trip with a status-bearing save — idempotent.
    trip.refresh_from_db()
    trip.save(update_fields=["status", "updated_at"])
    assert _trip_completed(driver).count() == 1


@pytest.mark.django_db
def test_non_completed_save_creates_no_notification(trip, driver):
    # Starting a trip (status -> IN_PROGRESS) must not produce a TRIP_COMPLETED row.
    TripService.start_trip(trip, driver)
    assert _trip_completed(driver).count() == 0


@pytest.mark.django_db
def test_create_does_not_fire_signal(trip, driver):
    # The fixture created a SCHEDULED trip — no notification on create.
    assert _trip_completed(driver).count() == 0


@pytest.mark.django_db
def test_save_without_status_in_update_fields_skips(route, bus, driver):
    # A COMPLETED trip saved WITHOUT "status" in update_fields must not produce one
    # (guards against unrelated field saves on an already-completed trip).
    completed = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.COMPLETED
    )
    # create() fires post_save with update_fields=None -> guard skips it.
    assert _trip_completed(driver).count() == 0
    completed.passenger_count = 12
    completed.save(update_fields=["passenger_count", "updated_at"])
    assert _trip_completed(driver).count() == 0
