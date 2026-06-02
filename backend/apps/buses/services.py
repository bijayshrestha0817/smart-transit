"""Domain logic for the buses app — views delegate here so they stay thin.

Multi-step mutations run inside ``transaction.atomic()`` so a partial failure
never leaves the DB half-updated. ``nearby_stops`` is deliberately DB-agnostic
(bounding box, not PostGIS) so it works on both the SQLite test DB and Postgres.
"""

from decimal import Decimal
from math import cos, radians

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Bus, BusStop, Route

User = get_user_model()

# Roughly 111 km per degree of latitude.
_KM_PER_DEGREE = 111.0


def assign_driver(bus: Bus, driver_id: int) -> Bus:
    """Assign a driver (role=driver) to a bus and persist the change."""
    with transaction.atomic():
        driver = User.objects.get(id=driver_id, role=User.Roles.DRIVER, is_deleted=False)
        bus.assigned_driver = driver
        bus.save(update_fields=["assigned_driver", "updated_at"])
    return bus


def set_maintenance(bus: Bus) -> Bus:
    """Flip a bus into the maintenance state."""
    with transaction.atomic():
        bus.status = Bus.Status.MAINTENANCE
        bus.save(update_fields=["status", "updated_at"])
    return bus


def replace_route_stops(route: Route, stops_data: list[dict]) -> list[BusStop]:
    """Atomically soft-delete the route's current stops and create the new set.

    Each entry in ``stops_data`` is a dict of ``{name, lat, lng, sequence}``; the
    ``route`` is bound from the argument. Returns the newly created stops.
    """
    with transaction.atomic():
        # Soft-delete (not hard) so any historical references survive; the
        # partial-unique constraint ignores tombstones, freeing the sequences.
        route.stops.all().delete()
        created = [BusStop.objects.create(route=route, **stop) for stop in stops_data]
    return created


def nearby_stops(queryset, lat: float, lng: float, radius_km: float):
    """Filter ``queryset`` to stops within ``radius_km`` of ``(lat, lng)``.

    Uses a bounding box (no PostGIS) so it runs identically on SQLite and
    Postgres. The box slightly over-includes corners vs. a true circle, which is
    acceptable for the "stops near me" UX.
    """
    dlat = radius_km / _KM_PER_DEGREE
    cos_lat = cos(radians(lat))
    if abs(cos_lat) < 1e-9:  # near the poles — avoid divide-by-zero
        dlng = 180.0
    else:
        dlng = radius_km / (_KM_PER_DEGREE * cos_lat)

    lat_d = Decimal(str(lat))
    lng_d = Decimal(str(lng))
    dlat_d = Decimal(str(dlat))
    dlng_d = Decimal(str(abs(dlng)))

    return queryset.filter(
        lat__range=(lat_d - dlat_d, lat_d + dlat_d),
        lng__range=(lng_d - dlng_d, lng_d + dlng_d),
    )
