"""Service-layer tests for AlertService: persist, acknowledge (idempotent), broadcast.

The broadcast is deferred to ``transaction.on_commit`` and is best-effort. We use pytest's
``django_capture_on_commit_callbacks`` to flush the callback, and patch ``broadcast_alert`` at
its definition site so we assert the producer fires without touching a real channel layer.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.alerts.enums import AlertSeverity, AlertStatus, AlertType
from apps.alerts.models import Alert
from apps.alerts.v1.service import AlertService

User = get_user_model()


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        email="admin@example.com",
        password="StrongPass123!",
        role=User.Roles.ADMIN,
        is_verified=True,
    )


@pytest.mark.django_db
def test_raise_alert_persists_open_row():
    alert = AlertService.raise_alert(
        type=AlertType.SOS, severity=AlertSeverity.CRITICAL, message="SOS from driver"
    )
    assert alert.pk is not None
    assert alert.status == AlertStatus.OPEN
    assert Alert.objects.filter(id=alert.id, severity=AlertSeverity.CRITICAL).exists()


@pytest.mark.django_db
def test_raise_alert_broadcasts_serialized_alert_on_commit(django_capture_on_commit_callbacks):
    with patch("apps.alerts.realtime.broadcast_alert") as broadcast:
        with django_capture_on_commit_callbacks(execute=True):
            alert = AlertService.raise_alert(
                type=AlertType.SOS, severity=AlertSeverity.CRITICAL, message="SOS"
            )
    broadcast.assert_called_once()
    data = broadcast.call_args.args[0]
    assert data["id"] == alert.id
    assert data["severity"] == AlertSeverity.CRITICAL
    assert data["status"] == AlertStatus.OPEN


@pytest.mark.django_db
def test_acknowledge_sets_status_and_actor(admin):
    alert = AlertService.raise_alert(
        type=AlertType.SOS, severity=AlertSeverity.CRITICAL, message="SOS"
    )
    acked = AlertService.acknowledge(alert, admin)
    assert acked.status == AlertStatus.ACKNOWLEDGED
    assert acked.acknowledged_at is not None
    assert acked.acknowledged_by_id == admin.id


@pytest.mark.django_db
def test_acknowledge_is_idempotent(admin):
    alert = AlertService.raise_alert(
        type=AlertType.SOS, severity=AlertSeverity.CRITICAL, message="SOS"
    )
    first = AlertService.acknowledge(alert, admin)
    at = first.acknowledged_at
    again = AlertService.acknowledge(first, admin)
    assert again.acknowledged_at == at  # second ack is a no-op


@pytest.mark.django_db
def test_feed_filters_by_status_and_severity():
    AlertService.raise_alert(type=AlertType.SOS, severity=AlertSeverity.CRITICAL, message="a")
    warn = AlertService.raise_alert(
        type=AlertType.OVERSPEED, severity=AlertSeverity.WARNING, message="b"
    )
    AlertService.acknowledge(warn, None)
    assert AlertService.feed(status=AlertStatus.OPEN).count() == 1
    assert AlertService.feed(severity=AlertSeverity.WARNING).count() == 1
