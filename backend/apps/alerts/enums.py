"""Enums for the alerts app."""

from django.db import models


class AlertType(models.TextChoices):
    # Only SOS is produced today (from a driver SOS log). The rest are reserved for the
    # P5 anomaly producers (overspeed/route-deviation detectors, maintenance-due job) so
    # the contract and the UI severity mapping are stable before those land.
    SOS = "sos", "SOS"
    OVERSPEED = "overspeed", "Overspeed"
    ROUTE_DEVIATION = "route_deviation", "Route deviation"
    MAINTENANCE_DUE = "maintenance_due", "Maintenance due"


class AlertSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class AlertStatus(models.TextChoices):
    OPEN = "open", "Open"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
