"""REST + RBAC tests for the driver logs API: log + SOS create, role gating, envelope.

Role auth uses ``client.force_authenticate(user=...)``. Body assertions read the
rendered ``{data, meta, errors}`` envelope.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.alerts.enums import AlertSeverity, AlertType
from apps.alerts.models import Alert
from apps.buses.models import Bus, Route
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.models import DriverLog
from apps.notifications.enums import NotificationType
from apps.notifications.models import Notification
from apps.trips.models import Trip

User = get_user_model()

PASSWORD = "StrongPass123!"
LOGS_URL = "/api/v1/driver/logs/"
SOS_URL = "/api/v1/driver/sos/"


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


@pytest.fixture
def other_driver(db):
    return User.objects.create_user(
        email="driver2@example.com", password=PASSWORD, role=User.Roles.DRIVER, is_verified=True
    )


@pytest.fixture
def route(db):
    return Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)


@pytest.fixture
def bus(db):
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


@pytest.fixture
def trip(route, driver, bus):
    return Trip.objects.create(bus=bus, route=route, driver=driver)


# ── Driver creates a log ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_driver_can_create_log(client, driver):
    client.force_authenticate(user=driver)
    resp = client.post(
        LOGS_URL, {"event_type": DriverLogEventType.DELAY, "notes": "traffic"}, format="json"
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["event_type"] == DriverLogEventType.DELAY
    assert body["notes"] == "traffic"
    assert body["trip"] is None
    assert DriverLog.objects.filter(id=body["id"]).exists()


@pytest.mark.django_db
def test_driver_create_log_envelope_shape(client, driver):
    client.force_authenticate(user=driver)
    resp = client.post(LOGS_URL, {"event_type": DriverLogEventType.NOTE}, format="json")
    assert resp.status_code == 201
    envelope = resp.json()
    assert "data" in envelope and "meta" in envelope and "errors" in envelope
    assert envelope["errors"] is None


@pytest.mark.django_db
def test_driver_create_log_with_owned_trip(client, driver, trip):
    client.force_authenticate(user=driver)
    resp = client.post(
        LOGS_URL, {"event_type": DriverLogEventType.FUEL, "trip": trip.id}, format="json"
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["trip"] == trip.id


@pytest.mark.django_db
def test_driver_create_log_unowned_trip_returns_400_invalid_trip(client, other_driver, trip):
    client.force_authenticate(user=other_driver)
    resp = client.post(
        LOGS_URL, {"event_type": DriverLogEventType.DELAY, "trip": trip.id}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "invalid_trip"
    assert DriverLog.objects.count() == 0


@pytest.mark.django_db
def test_driver_create_log_invalid_event_type_returns_400(client, driver):
    client.force_authenticate(user=driver)
    resp = client.post(LOGS_URL, {"event_type": "bogus"}, format="json")
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["field"] == "event_type"


@pytest.mark.django_db
def test_log_requires_auth(client):
    assert client.post(LOGS_URL, {"event_type": "note"}, format="json").status_code == 401


@pytest.mark.django_db
def test_log_forbidden_for_passenger_and_admin(client, passenger, admin):
    client.force_authenticate(user=passenger)
    assert client.post(LOGS_URL, {"event_type": "note"}, format="json").status_code == 403
    client.force_authenticate(user=admin)
    assert client.post(LOGS_URL, {"event_type": "note"}, format="json").status_code == 403


# ── Driver SOS ───────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_driver_can_raise_sos(client, driver, admin):
    client.force_authenticate(user=driver)
    resp = client.post(SOS_URL, {"notes": "engine fire"}, format="json")
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["event_type"] == DriverLogEventType.SOS
    assert DriverLog.objects.filter(id=body["id"], event_type=DriverLogEventType.SOS).exists()
    # The admin received one EMERGENCY notification.
    emergency = Notification.objects.filter(type=NotificationType.EMERGENCY, user=admin)
    assert emergency.count() == 1
    assert emergency.first().payload_json["log_id"] == body["id"]
    # …and the incident was recorded as a CRITICAL SOS alert in the incident log.
    alert = Alert.objects.get(type=AlertType.SOS)
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.payload_json["log_id"] == body["id"]


@pytest.mark.django_db
def test_sos_empty_body_is_ok(client, driver):
    client.force_authenticate(user=driver)
    resp = client.post(SOS_URL, {}, format="json")
    assert resp.status_code == 201
    assert resp.json()["data"]["event_type"] == DriverLogEventType.SOS


@pytest.mark.django_db
def test_sos_unowned_trip_returns_400_invalid_trip(client, other_driver, trip):
    client.force_authenticate(user=other_driver)
    resp = client.post(SOS_URL, {"trip": trip.id}, format="json")
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "invalid_trip"
    assert DriverLog.objects.count() == 0


@pytest.mark.django_db
def test_sos_broadcast_failure_still_returns_201(client, driver, admin):
    # A degraded fan-out (the alert producer raises) must not break the committed SOS log.
    from unittest.mock import patch

    from apps.alerts.v1.service import AlertService

    client.force_authenticate(user=driver)
    with patch.object(AlertService, "raise_alert", side_effect=RuntimeError("channel layer down")):
        resp = client.post(SOS_URL, {"notes": "still works"}, format="json")
    assert resp.status_code == 201
    assert DriverLog.objects.filter(id=resp.json()["data"]["id"]).exists()


@pytest.mark.django_db
def test_sos_requires_auth(client):
    assert client.post(SOS_URL, {}, format="json").status_code == 401


@pytest.mark.django_db
def test_sos_forbidden_for_passenger_and_admin(client, passenger, admin):
    client.force_authenticate(user=passenger)
    assert client.post(SOS_URL, {}, format="json").status_code == 403
    client.force_authenticate(user=admin)
    assert client.post(SOS_URL, {}, format="json").status_code == 403
