"""Alert model — the operations incident log behind the admin alerts feed.

Inherits ``TimeStampedSoftDeleteModel`` (timestamps + soft delete). One row per incident:
its ``type`` (what happened), ``severity`` (how bad), a human ``message``, optional links to
the ``trip``/``driver`` it concerns, and a free-form ``payload_json`` for type-specific extras.
``status`` tracks the operator workflow (OPEN → ACKNOWLEDGED) with who/when on the ack.

Today the sole producer is a driver SOS (``AlertService.raise_alert`` from the driver-logs
SOS path); the other ``AlertType`` values are reserved for the P5 anomaly producers. Reference
links are ``SET_NULL`` (an alert outlives the trip/driver it references — the incident record
must never be dropped or blocked). The ``(status, -created_at)`` index backs the default
"open incidents, newest first" feed.
"""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedSoftDeleteModel

from .enums import AlertSeverity, AlertStatus, AlertType


class Alert(TimeStampedSoftDeleteModel):
    """One operations incident (SOS now; anomalies later) shown in the admin alerts feed."""

    Type = AlertType  # enums live in enums.py; aliased so Alert.Type.X keeps working
    Severity = AlertSeverity
    Status = AlertStatus

    type = models.CharField(max_length=20, choices=Type.choices)
    severity = models.CharField(max_length=8, choices=Severity.choices, default=Severity.WARNING)
    message = models.CharField(max_length=255)
    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raised_alerts",
    )
    payload_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
    )

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "alerts"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Alert #{self.pk} ({self.type}/{self.severity}/{self.status})"
