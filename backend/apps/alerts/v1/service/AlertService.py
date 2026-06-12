"""Business logic for alerts — the incident log + live broadcast producer.

``@staticmethod`` throughout; mutations run inside ``transaction.atomic()``. ``raise_alert``
is the one place an incident is born: it persists the row, then (AFTER commit) broadcasts the
serialized alert onto the ``alerts.admin`` group so admin feeds only ever learn of a persisted
incident. The broadcast is best-effort — a channel-layer failure never undoes the committed row.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.alerts.enums import AlertStatus
from apps.alerts.models import Alert
from apps.alerts.repository import AlertRepository

logger = logging.getLogger(__name__)


class AlertService:
    @staticmethod
    def raise_alert(
        *, type, severity, message: str, trip=None, driver=None, payload: dict | None = None
    ) -> Alert:
        """Persist an incident and broadcast it on commit. Returns the committed Alert."""
        with transaction.atomic():
            alert = AlertRepository.create(
                {
                    "type": type,
                    "severity": severity,
                    "message": message,
                    "trip": trip,
                    "driver": driver,
                    "payload_json": payload or {},
                }
            )
            # Broadcast only after the row lands, so a live subscriber never sees an alert
            # that a rollback then erased. Best-effort: deferred and self-guarding.
            transaction.on_commit(lambda: AlertService._broadcast(alert.id))
        return alert

    @staticmethod
    def _broadcast(alert_id) -> None:
        """Serialize the committed alert and push it to the admin group. Never raises."""
        try:
            from apps.alerts.realtime import broadcast_alert
            from apps.alerts.v1.serializers import AlertSerializer

            alert = AlertRepository.get_by_id(alert_id)
            if alert is None:
                return
            broadcast_alert(AlertSerializer(alert).data)
        except Exception:  # noqa: BLE001 — broadcast is best-effort; never break the producer
            logger.warning("alert broadcast failed for alert %s", alert_id, exc_info=True)

    @staticmethod
    def acknowledge(alert: Alert, by_user) -> Alert:
        """Mark an open alert acknowledged (idempotent: a 2nd ack is a no-op)."""
        if alert.status == AlertStatus.ACKNOWLEDGED:
            return alert
        with transaction.atomic():
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = by_user
            alert.save(update_fields=["status", "acknowledged_at", "acknowledged_by", "updated_at"])
        return alert

    @staticmethod
    def feed(*, status: str | None = None, severity: str | None = None):
        """Queryset for the admin feed (cursor-paged by the view), newest first."""
        qs = AlertRepository.feed()
        if status:
            qs = qs.filter(status=status)
        if severity:
            qs = qs.filter(severity=severity)
        return qs
