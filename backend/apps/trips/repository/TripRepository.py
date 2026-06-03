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
    def create(cls, data: dict) -> Trip:
        return Trip.objects.create(**data)

    @classmethod
    def in_progress(cls):
        return cls.active().filter(status=TripStatus.IN_PROGRESS)

    @classmethod
    def on_route_in_progress(cls, route_id):
        return cls.in_progress().filter(route_id=route_id)
