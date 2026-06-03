"""Domain models for trips and their GPS breadcrumb stream (er-diagram §4).

Both inherit ``TimeStampedSoftDeleteModel`` (timestamps + soft delete). A ``Trip``
is one run of a ``Bus`` along a ``Route`` driven by a ``driver`` user; reference
data (bus/route/driver) is ``on_delete=PROTECT`` so a trip can never dangle, while
its ``GpsLocation`` breadcrumbs cascade (``on_delete=CASCADE``) since they have no
meaning without their trip. Coordinates use ``DECIMAL(9,6)`` like the rest of the
schema.
"""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedSoftDeleteModel

from .enums import TripStatus


class Trip(TimeStampedSoftDeleteModel):
    """One run of a bus along a route, driven by an assigned driver."""

    Status = TripStatus  # enum lives in enums.py; aliased so Trip.Status.X keeps working

    bus = models.ForeignKey(
        "buses.Bus",
        on_delete=models.PROTECT,
        related_name="trips",
    )
    route = models.ForeignKey(
        "buses.Route",
        on_delete=models.PROTECT,
        related_name="trips",
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="driven_trips",
        limit_choices_to={"role": "driver"},
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    passenger_count = models.PositiveIntegerField(null=True, blank=True)

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "trips"
        indexes = [
            models.Index(fields=["status", "route"]),
            models.Index(fields=["bus", "start_time"]),
        ]

    def __str__(self) -> str:
        return f"Trip #{self.pk} ({self.status})"


class GpsLocation(TimeStampedSoftDeleteModel):
    """A single GPS breadcrumb for a trip — high-volume, append-mostly telemetry."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="gps_locations")
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    speed = models.DecimalField(max_digits=5, decimal_places=2)
    heading = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    timestamp = models.DateTimeField()

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "gps_locations"
        indexes = [
            models.Index(fields=["trip", "-timestamp"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.lat},{self.lng} @ {self.timestamp:%Y-%m-%d %H:%M:%S}"
