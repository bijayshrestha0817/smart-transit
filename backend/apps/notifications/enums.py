"""Enums for the notifications app."""

from django.db import models


class NotificationType(models.TextChoices):
    BUS_ARRIVING = "bus_arriving", "Bus arriving"
    ROUTE_DELAY = "route_delay", "Route delay"
    EMERGENCY = "emergency", "Emergency"
    MAINTENANCE_DUE = "maintenance_due", "Maintenance due"
    TRIP_COMPLETED = "trip_completed", "Trip completed"
