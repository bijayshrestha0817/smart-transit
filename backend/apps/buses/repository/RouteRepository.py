"""Data access for Route. All Route ORM lives here."""

from django.db.models import Prefetch

from apps.buses.models import BusStop, Route
from apps.common.repository import BaseRepository


class RouteRepository(BaseRepository):
    model = Route

    @classmethod
    def list_queryset(cls):
        """Base queryset for list endpoints (filter backends + pagination layer on top)."""
        return Route.objects.all()

    @classmethod
    def get_by_id(cls, route_id):
        return Route.objects.filter(id=route_id).first()

    @classmethod
    def detail_queryset(cls):
        """Queryset whose rows carry ``ordered_stops`` (prefetched in sequence order),
        so the detail serializer never queries. Used for retrieve + post-write responses."""
        return Route.objects.prefetch_related(
            Prefetch(
                "stops",
                queryset=BusStop.objects.order_by("sequence"),
                to_attr="ordered_stops",
            )
        )

    @classmethod
    def get_with_stops(cls, route_id):
        return cls.detail_queryset().filter(id=route_id).first()

    @classmethod
    def create(cls, data: dict) -> Route:
        return Route.objects.create(**data)
