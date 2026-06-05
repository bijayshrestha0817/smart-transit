"""Maintenance log model — the fleet's service-history audit trail (er-diagram §11).

Inherits ``TimeStampedSoftDeleteModel`` (timestamps + soft delete). Each row records one
servicing event for a bus: the kind of service, its cost, when it happened, and (optionally)
when the next service is due. ``cost`` is ``DECIMAL`` (money never touches float) and must be
``>= 0``. ``serviced_at`` is the event time, distinct from the audit ``created_at``.

``bus`` is ``PROTECT`` — a bus with maintenance history can't be hard-deleted out from under
its records. ``next_due`` seeds the future P5-AI ``MAINTENANCE_DUE`` check (a nightly job will
flag buses whose ``next_due`` has passed). The ``(bus, -serviced_at)`` index backs a bus's
own service-history query (newest first).
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TimeStampedSoftDeleteModel


class MaintenanceLog(TimeStampedSoftDeleteModel):
    """One servicing event for a bus (service type, cost, when, next due)."""

    bus = models.ForeignKey(
        "buses.Bus",
        on_delete=models.PROTECT,
        related_name="maintenance_logs",
    )
    service_type = models.CharField(max_length=120)
    # Money is Decimal, never float; ``>= 0`` so a seed/admin can't push a negative cost.
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    serviced_at = models.DateTimeField()
    # Seeds the future P5-AI MAINTENANCE_DUE check (nightly job flags overdue buses).
    next_due = models.DateField(null=True, blank=True)

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "maintenance_logs"
        indexes = [
            models.Index(fields=["bus", "-serviced_at"]),
        ]

    def __str__(self) -> str:
        return f"MaintenanceLog #{self.pk} ({self.service_type}) for bus {self.bus_id}"
