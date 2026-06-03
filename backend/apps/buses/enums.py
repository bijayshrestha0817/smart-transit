"""Enums for the buses app."""

from django.db import models


class BusStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    IDLE = "idle", "Idle"
    MAINTENANCE = "maintenance", "Maintenance"
    RETIRED = "retired", "Retired"
