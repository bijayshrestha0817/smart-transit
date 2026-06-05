"""Enums for the driver_logs app."""

from django.db import models


class DriverLogEventType(models.TextChoices):
    DELAY = "delay", "Delay"
    BREAKDOWN = "breakdown", "Breakdown"
    FUEL = "fuel", "Fuel"
    SOS = "sos", "SOS"
    NOTE = "note", "Note"
