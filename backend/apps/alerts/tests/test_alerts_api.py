"""REST + RBAC tests for the admin alerts feed: list (cursor + filters), acknowledge, gating.

Role auth uses ``client.force_authenticate(user=...)``. Body assertions read the rendered
``{data, meta, errors}`` envelope.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.alerts.enums import AlertSeverity, AlertStatus, AlertType
from apps.alerts.models import Alert

User = get_user_model()

PASSWORD = "StrongPass123!"
ALERTS_URL = "/api/v1/admin/alerts/"


def ack_url(alert_id) -> str:
    return f"/api/v1/admin/alerts/{alert_id}/acknowledge/"


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
def sos_alert(db):
    return Alert.objects.create(
        type=AlertType.SOS, severity=AlertSeverity.CRITICAL, message="SOS from driver #1"
    )


@pytest.mark.django_db
def test_admin_can_list_alerts(client, admin, sos_alert):
    client.force_authenticate(user=admin)
    resp = client.get(ALERTS_URL)
    assert resp.status_code == 200
    envelope = resp.json()
    assert isinstance(envelope["data"], list)
    assert envelope["meta"]["pagination"]["page_size"] == 20
    row = next(a for a in envelope["data"] if a["id"] == sos_alert.id)
    assert row["type"] == AlertType.SOS
    assert row["severity"] == AlertSeverity.CRITICAL
    assert row["status"] == AlertStatus.OPEN


@pytest.mark.django_db
def test_list_filters_by_status(client, admin, sos_alert):
    acked = Alert.objects.create(
        type=AlertType.OVERSPEED,
        severity=AlertSeverity.WARNING,
        message="overspeed",
        status=AlertStatus.ACKNOWLEDGED,
    )
    client.force_authenticate(user=admin)
    resp = client.get(ALERTS_URL, {"status": AlertStatus.OPEN})
    ids = {a["id"] for a in resp.json()["data"]}
    assert sos_alert.id in ids
    assert acked.id not in ids


@pytest.mark.django_db
def test_list_filters_by_severity(client, admin, sos_alert):
    Alert.objects.create(
        type=AlertType.OVERSPEED, severity=AlertSeverity.WARNING, message="overspeed"
    )
    client.force_authenticate(user=admin)
    resp = client.get(ALERTS_URL, {"severity": AlertSeverity.CRITICAL})
    sevs = {a["severity"] for a in resp.json()["data"]}
    assert sevs == {AlertSeverity.CRITICAL}


@pytest.mark.django_db
def test_admin_can_acknowledge(client, admin, sos_alert):
    client.force_authenticate(user=admin)
    resp = client.post(ack_url(sos_alert.id))
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == AlertStatus.ACKNOWLEDGED
    sos_alert.refresh_from_db()
    assert sos_alert.status == AlertStatus.ACKNOWLEDGED
    assert sos_alert.acknowledged_by_id == admin.id


@pytest.mark.django_db
def test_acknowledge_unknown_returns_404(client, admin):
    client.force_authenticate(user=admin)
    assert client.post(ack_url(999999)).status_code == 404


@pytest.mark.django_db
def test_alerts_forbidden_for_non_admin(client, passenger, driver, sos_alert):
    client.force_authenticate(user=passenger)
    assert client.get(ALERTS_URL).status_code == 403
    assert client.post(ack_url(sos_alert.id)).status_code == 403
    client.force_authenticate(user=driver)
    assert client.get(ALERTS_URL).status_code == 403


@pytest.mark.django_db
def test_alerts_requires_auth(client, sos_alert):
    assert client.get(ALERTS_URL).status_code == 401
    assert client.post(ack_url(sos_alert.id)).status_code == 401
