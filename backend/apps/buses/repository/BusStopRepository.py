"""Data access for BusStop, including the DB-agnostic proximity filter."""

from decimal import Decimal
from math import cos, radians

from apps.buses.models import BusStop
from apps.common.repository import BaseRepository

# Roughly 111 km per degree of latitude.
_KM_PER_DEGREE = 111.0


class BusStopRepository(BaseRepository):
    model = BusStop

    @classmethod
    def get_by_id(cls, stop_id):
        return BusStop.objects.filter(id=stop_id).first()

    @classmethod
    def all_stops(cls):
        return BusStop.objects.all()

    @classmethod
    def delete_for_route(cls, route) -> None:
        """Soft-delete a route's current stops (tombstones free the unique sequences)."""
        route.stops.all().delete()

    @classmethod
    def bulk_create_for_route(cls, route, stops_data: list[dict]) -> list[BusStop]:
        return [BusStop.objects.create(route=route, **stop) for stop in stops_data]

    @classmethod
    def nearby(cls, queryset, lat: float, lng: float, radius_km: float):
        """Filter ``queryset`` to stops within ``radius_km`` of ``(lat, lng)``.

        Bounding box (no PostGIS) so it runs identically on SQLite and Postgres; the
        box slightly over-includes corners vs. a true circle — fine for "stops near me".
        """
        dlat = radius_km / _KM_PER_DEGREE
        cos_lat = cos(radians(lat))
        dlng = 180.0 if abs(cos_lat) < 1e-9 else radius_km / (_KM_PER_DEGREE * cos_lat)

        lat_d = Decimal(str(lat))
        lng_d = Decimal(str(lng))
        dlat_d = Decimal(str(dlat))
        dlng_d = Decimal(str(abs(dlng)))

        return queryset.filter(
            lat__range=(lat_d - dlat_d, lat_d + dlat_d),
            lng__range=(lng_d - dlng_d, lng_d + dlng_d),
        )
