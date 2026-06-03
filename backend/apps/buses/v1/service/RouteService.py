"""Business logic for routes and their stops."""

from django.db import transaction

from apps.buses.models import BusStop, Route
from apps.buses.repository import BusStopRepository, RouteRepository


class RouteService:
    @staticmethod
    def create(data: dict) -> Route:
        with transaction.atomic():
            return RouteRepository.create(data)

    @staticmethod
    def update(route: Route, data: dict) -> Route:
        with transaction.atomic():
            return RouteRepository.apply_update(route, data)

    @staticmethod
    def replace_stops(route: Route, stops_data: list[dict]) -> list[BusStop]:
        """Atomically soft-delete the route's current stops and create the new set."""
        with transaction.atomic():
            BusStopRepository.delete_for_route(route)
            return BusStopRepository.bulk_create_for_route(route, stops_data)
