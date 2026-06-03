"""Data access for GpsLocation. All GpsLocation ORM lives here."""

from django.db.models import OuterRef, Subquery

from apps.common.repository import BaseRepository
from apps.trips.models import GpsLocation


class GpsLocationRepository(BaseRepository):
    model = GpsLocation

    @classmethod
    def bulk_insert(cls, rows) -> list[GpsLocation]:
        return GpsLocation.objects.bulk_create(rows)

    @classmethod
    def latest_for_trip(cls, trip_id):
        # last-position row feeds serialized payloads — select what the serializer reads.
        return (
            GpsLocation.objects.filter(trip_id=trip_id)
            .select_related("trip", "trip__bus", "trip__route")
            .order_by("-timestamp")
            .first()
        )

    @classmethod
    def latest_for_trips(cls, trip_ids):
        """Return the latest GPS breadcrumb per trip (one newest row for each trip).

        Portable across SQLite (tests) and Postgres (prod): uses a correlated
        subquery rather than the Postgres-only ``.distinct("trip_id")``.
        """
        latest_id = (
            GpsLocation.objects.filter(trip_id=OuterRef("trip_id"))
            .order_by("-timestamp")
            .values("id")[:1]
        )
        return GpsLocation.objects.filter(
            trip_id__in=trip_ids, id=Subquery(latest_id)
        ).select_related("trip", "trip__bus", "trip__route")
