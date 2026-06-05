"""Driver log model — the driver's operational audit trail (er-diagram §4).

Inherits ``TimeStampedSoftDeleteModel`` (timestamps + soft delete). Each row records
one event a driver reports during operations: a delay, breakdown, fuel stop, free-form
note, or an SOS. The optional ``trip`` ties the log to a run (the service enforces it
belongs to the reporting driver). ``timestamp`` is server-stamped at creation — the
event time, distinct from the audit ``created_at``. The ``(driver, -timestamp)`` index
backs a driver's own log-history query.

An ``event_type == sos`` row is what fires the real-time admin emergency alert + the
per-admin EMERGENCY notification (the side-effect lives in the service, keyed on the
type, so ``/driver/sos/`` and a ``/driver/logs/`` post with ``event_type=sos`` behave
identically). The committed row is the audit record; fan-out is best-effort.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedSoftDeleteModel

from .enums import DriverLogEventType


class DriverLog(TimeStampedSoftDeleteModel):
    """One operational event reported by a driver (delay/breakdown/fuel/sos/note)."""

    EventType = DriverLogEventType  # enum lives in enums.py; aliased for DriverLog.EventType.X

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="driver_logs",
        limit_choices_to={"role": "driver"},
    )
    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_logs",
    )
    event_type = models.CharField(max_length=12, choices=EventType.choices)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "driver_logs"
        indexes = [
            models.Index(fields=["driver", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"DriverLog #{self.pk} ({self.event_type}) by driver {self.driver_id}"
