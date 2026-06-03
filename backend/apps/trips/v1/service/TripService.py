"""Business logic for trips. Views (and, later, consumers) call these; these call
repositories. All ``@staticmethod``; mutations run inside ``transaction.atomic()``;
domain rules raise ``apps.trips.exceptions``."""

from django.db import transaction
from django.utils import timezone

from apps.trips.enums import TripStatus
from apps.trips.exceptions import (
    TripAlreadyStartedError,
    TripNotAssignedError,
    TripNotInProgressError,
)
from apps.trips.models import GpsLocation, Trip
from apps.trips.repository import GpsLocationRepository, TripRepository


class TripService:
    @staticmethod
    def create(data: dict) -> Trip:
        """Admin scheduling — persist a new (SCHEDULED) trip."""
        with transaction.atomic():
            return TripRepository.create(data)

    @staticmethod
    def update(trip: Trip, data: dict) -> Trip:
        with transaction.atomic():
            return TripRepository.apply_update(trip, data)

    @staticmethod
    def start_trip(trip: Trip, by_user) -> Trip:
        if trip.driver_id != by_user.id:
            raise TripNotAssignedError()
        if trip.status != TripStatus.SCHEDULED:
            raise TripAlreadyStartedError()
        with transaction.atomic():
            trip.status = TripStatus.IN_PROGRESS
            trip.start_time = timezone.now()
            trip.save(update_fields=["status", "start_time", "updated_at"])
        return trip

    @staticmethod
    def end_trip(trip: Trip, by_user) -> Trip:
        if trip.driver_id != by_user.id:
            raise TripNotAssignedError()
        if trip.status != TripStatus.IN_PROGRESS:
            raise TripNotInProgressError()
        with transaction.atomic():
            trip.status = TripStatus.COMPLETED
            trip.end_time = timezone.now()
            trip.save(update_fields=["status", "end_time", "updated_at"])
        # Announce completion on the trip.<id> group AFTER the commit so subscribers
        # only learn of state that's actually persisted. Imported locally to avoid an
        # import cycle (realtime -> service) and a hard channels dependency at module load.
        from realtime.broadcast import broadcast_trip_event

        broadcast_trip_event(trip.id, "TRIP_COMPLETED")
        return trip

    @staticmethod
    def set_passenger_count(trip: Trip, by_user, count: int) -> Trip:
        if trip.driver_id != by_user.id:
            raise TripNotAssignedError()
        with transaction.atomic():
            trip.passenger_count = count
            trip.save(update_fields=["passenger_count", "updated_at"])
        return trip

    @staticmethod
    def ingest_gps(trip: Trip, by_user, points) -> int:
        """Persist a batch of validated GPS points (offline-flush / REST batch).

        Asserts ``by_user`` is the driver assigned to ``trip`` (raises
        ``TripNotAssignedError`` otherwise) so callers that bypass the DRF-scoped
        queryset — e.g. the future WS flush — stay safe. The batch carries CLIENT
        timestamps for offline points, so the provided ``timestamp`` is used as-is.
        Shared by the future WS flush and the REST endpoint. Returns the number of
        rows inserted.
        """
        if trip.driver_id != by_user.id:
            raise TripNotAssignedError()
        rows = [
            GpsLocation(
                trip=trip,
                lat=point["lat"],
                lng=point["lng"],
                speed=point["speed"],
                heading=point.get("heading"),
                timestamp=point["timestamp"],
            )
            for point in points
        ]
        with transaction.atomic():
            GpsLocationRepository.bulk_insert(rows)
        return len(rows)

    @staticmethod
    def active_on_route(route_id) -> list[dict]:
        """IN_PROGRESS trips on a route, each paired with its latest GPS breadcrumb."""
        trips = list(TripRepository.on_route_in_progress(route_id))
        return TripService._pair_with_last_position(trips)

    @staticmethod
    def fleet_snapshot() -> list[dict]:
        """All IN_PROGRESS trips, each paired with its latest GPS breadcrumb."""
        trips = list(TripRepository.in_progress())
        return TripService._pair_with_last_position(trips)

    @staticmethod
    def _pair_with_last_position(trips: list[Trip]) -> list[dict]:
        positions = {
            row.trip_id: row
            for row in GpsLocationRepository.latest_for_trips([t.id for t in trips])
        }
        return [{"trip": trip, "last_position": positions.get(trip.id)} for trip in trips]
