"""Data access for Trip. All Trip ORM lives here."""

from apps.common.repository import BaseRepository
from apps.trips.enums import TripStatus
from apps.trips.models import Trip


class TripRepository(BaseRepository):
    model = Trip

    @classmethod
    def active(cls):
        # bus/route/driver are read on every trip response — select them up front.
        return Trip.objects.select_related("bus", "route", "driver")

    @classmethod
    def get_by_id(cls, trip_id):
        return cls.active().filter(id=trip_id).first()

    @classmethod
    def get_with_stops(cls, trip_id):
        # Single-trip read for the ETA endpoint: route stops prefetched (ordered by the
        # model's Meta ordering) so EtaService walks them with no extra query. Any status —
        # the view distinguishes 404 (no such trip) from an "unavailable" ETA.
        return cls.active().prefetch_related("route__stops").filter(id=trip_id).first()

    @classmethod
    def create(cls, data: dict) -> Trip:
        return Trip.objects.create(**data)

    @classmethod
    def in_progress(cls):
        # Prefetch route stops: the live-tracking reads (fleet snapshot, active-on-route)
        # compute a per-trip ETA over the stops, and this is their only caller path.
        return cls.active().prefetch_related("route__stops").filter(status=TripStatus.IN_PROGRESS)

    @classmethod
    def on_route_in_progress(cls, route_id):
        return cls.in_progress().filter(route_id=route_id)
