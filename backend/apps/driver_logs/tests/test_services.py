"""Service-layer tests: create_log persistence, trip-ownership rule, and SOS fan-out.

SOS side-effects run under ``CELERY_TASK_ALWAYS_EAGER`` (set in test settings). The
EMERGENCY notification ROWS are created synchronously inside ``create_log`` (only async
delivery is deferred to on_commit), so the rows are assertable directly. A broadcast or
notify failure must NEVER break the committed SOS log — the audit record that matters.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.buses.models import Bus, Route
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.exceptions import InvalidTripForLogError
from apps.driver_logs.models import DriverLog
from apps.driver_logs.v1.service import DriverLogService
from apps.notifications.enums import NotificationType
from apps.notifications.models import Notification
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


@pytest.fixture
def admins(db) -> list[User]:
    return [
        User.objects.create_user(
            email=f"admin{i}@smart-transit.ai", password="Demo1234!", role=User.Roles.ADMIN
        )
        for i in range(3)
    ]


# ── create_log ───────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_create_log_persists(driver):
    log = DriverLogService.create_log(driver, DriverLogEventType.NOTE, notes="checked engine")
    assert log.id is not None
    assert log.driver_id == driver.id
    assert log.event_type == DriverLogEventType.NOTE
    assert log.notes == "checked engine"
    assert log.trip_id is None
    assert DriverLog.objects.filter(id=log.id).exists()


@pytest.mark.django_db
def test_create_log_with_owned_trip(trip, driver):
    log = DriverLogService.create_log(driver, DriverLogEventType.DELAY, trip=trip)
    assert log.trip_id == trip.id


@pytest.mark.django_db
def test_create_log_with_owned_trip_by_id(trip, driver):
    log = DriverLogService.create_log(driver, DriverLogEventType.DELAY, trip=trip.id)
    assert log.trip_id == trip.id


@pytest.mark.django_db
def test_create_log_trip_not_owned_raises(trip, other_driver):
    with pytest.raises(InvalidTripForLogError) as exc:
        DriverLogService.create_log(other_driver, DriverLogEventType.DELAY, trip=trip.id)
    assert exc.value.status_code == 400
    assert exc.value.get_codes() == "invalid_trip"
    assert DriverLog.objects.count() == 0


@pytest.mark.django_db
def test_create_log_missing_trip_raises(driver):
    with pytest.raises(InvalidTripForLogError):
        DriverLogService.create_log(driver, DriverLogEventType.DELAY, trip=999999)
    assert DriverLog.objects.count() == 0


# ── SOS fan-out ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_sos_creates_one_emergency_notification_per_admin(driver, admins):
    with patch("apps.driver_logs.realtime.push_alert") as push:
        log = DriverLogService.create_log(driver, DriverLogEventType.SOS, notes="help!")
    # One EMERGENCY notification per admin.
    emergency = Notification.objects.filter(type=NotificationType.EMERGENCY)
    assert emergency.count() == len(admins)
    assert {n.user_id for n in emergency} == {a.id for a in admins}
    for n in emergency:
        assert n.payload_json["log_id"] == log.id
        assert n.payload_json["driver_id"] == driver.id
    # The broadcast was attempted.
    assert push.called


@pytest.mark.django_db
def test_sos_broadcast_attempted(driver, admins):
    with patch("apps.driver_logs.realtime.push_alert") as push:
        log = DriverLogService.create_log(driver, DriverLogEventType.SOS)
    push.assert_called_once()
    payload = push.call_args.args[0]
    assert payload["event"] == "SOS"
    assert payload["log_id"] == log.id
    assert payload["driver_id"] == driver.id


@pytest.mark.django_db
def test_non_sos_log_does_not_fan_out(driver, admins):
    with patch("apps.driver_logs.realtime.push_alert") as push:
        DriverLogService.create_log(driver, DriverLogEventType.DELAY)
    assert not push.called
    assert Notification.objects.filter(type=NotificationType.EMERGENCY).count() == 0


@pytest.mark.django_db
def test_sos_broadcast_failure_does_not_break_persist(driver, admins):
    # Patch the broadcast helper to raise: the SOS log must still commit (best-effort).
    with patch(
        "apps.driver_logs.realtime.push_alert",
        side_effect=RuntimeError("channel layer down"),
    ):
        log = DriverLogService.create_log(driver, DriverLogEventType.SOS)
    assert DriverLog.objects.filter(id=log.id).exists()


@pytest.mark.django_db
def test_sos_notify_failure_does_not_break_persist(driver, admins):
    # Patch the notification create to raise: the SOS log must still commit. patch.object
    # targets the class directly (the v1.service package re-exports a class whose name
    # collides with its defining submodule, so a string target is ambiguous to mock).
    from apps.notifications.v1.service import NotificationService

    with patch.object(NotificationService, "create", side_effect=RuntimeError("db gone")):
        log = DriverLogService.create_log(driver, DriverLogEventType.SOS)
    assert DriverLog.objects.filter(id=log.id).exists()
