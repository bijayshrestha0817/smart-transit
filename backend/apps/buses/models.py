"""Domain models for routes, stops, and the bus fleet (er-diagram §3).

All three inherit ``TimeStampedSoftDeleteModel`` (timestamps + soft delete). Per
the diagram's conventions: ``DECIMAL(9,6)`` coordinates, ``TextChoices`` enums,
``on_delete=PROTECT`` for reference data, and partial unique constraints
``WHERE is_deleted=false`` so soft-delete tombstones never block reuse of a value
(e.g. a plate or a stop sequence).
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedSoftDeleteModel

from .enums import BusStatus

# Hex colour like ``#1E88E5`` (3- or 6-digit) — drives the per-route map polyline.
HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
    message="Enter a valid hex colour, e.g. #1E88E5.",
    code="invalid_color",
)


class Route(TimeStampedSoftDeleteModel):
    """A named transit route with an encoded polyline and baseline duration."""

    name = models.CharField(max_length=120)
    # Encoded path points for the map; static baseline the AI ETA later refines.
    polyline_json = models.JSONField(default=list, blank=True)
    estimated_duration = models.PositiveIntegerField(help_text="Baseline duration in minutes.")
    color = models.CharField(max_length=7, validators=[HEX_COLOR_VALIDATOR])

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "routes"

    def __str__(self) -> str:
        return self.name


class BusStop(TimeStampedSoftDeleteModel):
    """An ordered stop along a route. ``(lat,lng)`` feed map markers + geofencing."""

    name = models.CharField(max_length=120)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="stops")
    sequence = models.PositiveIntegerField(help_text="Order along the route.")

    class Meta:
        db_table = "bus_stops"
        ordering = ("route", "sequence")
        get_latest_by = "created_at"
        indexes = [models.Index(fields=["route", "sequence"])]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "sequence"],
                condition=Q(is_deleted=False),
                name="uniq_busstop_route_sequence_active",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} (#{self.sequence})"


class Bus(TimeStampedSoftDeleteModel):
    """A fleet vehicle. ``assigned_driver`` is nullable so a bus survives driver
    reassignment (``SET_NULL``)."""

    Status = BusStatus  # enum lives in enums.py; aliased so Bus.Status.X keeps working

    plate = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IDLE)
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_buses",
        limit_choices_to={"role": "driver"},
    )

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "buses"
        indexes = [models.Index(fields=["status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["plate"],
                condition=Q(is_deleted=False),
                name="uniq_bus_plate_active",
            )
        ]

    def __str__(self) -> str:
        return f"{self.plate} ({self.status})"
