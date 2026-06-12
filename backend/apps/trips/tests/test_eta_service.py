"""Unit tests for the baseline ETA heuristic (``EtaService.estimate``).

Real models (no factory-boy, matching the suite style), but the service itself is ORM-free —
these just give it well-shaped objects. Coordinates are Kathmandu-ish; exact minutes aren't
asserted (the heuristic is approximate), only the source, sign, and next-stop selection.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.buses.models import Bus, BusStop, Route
from apps.trips.enums import TripStatus
from apps.trips.models import GpsLocation, Trip
from apps.trips.v1.service import EtaService

User = get_user_model()


@pytest.fixture
def route(db):
    return Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=40)


@pytest.fixture
def stops(route):
    coords = [
        ("Koteshwor", "27.700000", "85.300000", 1),
        ("Tinkune", "27.720000", "85.320000", 2),
        ("Baneshwor", "27.740000", "85.340000", 3),
    ]
    return [
        BusStop.objects.create(route=route, name=n, lat=Decimal(lat), lng=Decimal(lng), sequence=s)
        for n, lat, lng, s in coords
    ]


@pytest.fixture
def trip(route, db):
    driver = User.objects.create_user(
        email="d@example.com", password="StrongPass123!", role=User.Roles.DRIVER, is_verified=True
    )
    bus = Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)
    return Trip.objects.create(
        bus=bus,
        route=route,
        driver=driver,
        status=TripStatus.IN_PROGRESS,
        start_time=timezone.now(),
    )


def _gps(trip, lat, lng, speed):
    return GpsLocation(
        trip=trip,
        lat=Decimal(lat),
        lng=Decimal(lng),
        speed=Decimal(speed),
        heading=None,
        timestamp=timezone.now(),
    )


@pytest.mark.django_db
def test_gps_estimate_picks_stop_ahead(trip, stops):
    # Sitting just past stop 1, moving at 30 km/h → next stop is stop 2 (Tinkune).
    pos = _gps(trip, "27.701000", "85.301000", "30.00")
    eta = EtaService.estimate(trip, pos, stops)
    assert eta["source"] == "gps"
    assert eta["next_stop"] == "Tinkune"
    assert eta["seconds"] is not None and eta["seconds"] > 0
    assert eta["minutes"] == round(eta["seconds"] / 60)


@pytest.mark.django_db
def test_gps_estimate_at_terminus_targets_last_stop(trip, stops):
    # Near the final stop → target is the terminus itself (arriving), still a GPS estimate.
    pos = _gps(trip, "27.739000", "85.339000", "25.00")
    eta = EtaService.estimate(trip, pos, stops)
    assert eta["source"] == "gps"
    assert eta["next_stop"] == "Baneshwor"


@pytest.mark.django_db
def test_low_speed_falls_back_to_an_average_not_none(trip, stops):
    # A near-zero live speed must not divide-by-zero or return None — it falls back to the
    # route-average (or city-default) speed and still yields a positive estimate.
    pos = _gps(trip, "27.701000", "85.301000", "0.00")
    eta = EtaService.estimate(trip, pos, stops)
    assert eta["source"] == "gps"
    assert eta["seconds"] is not None and eta["seconds"] > 0


@pytest.mark.django_db
def test_schedule_fallback_when_no_gps(trip, stops):
    # No GPS fix yet, but the trip is running with a baseline duration → schedule estimate.
    eta = EtaService.estimate(trip, None, stops)
    assert eta["source"] == "schedule"
    assert eta["next_stop"] is None
    assert eta["minutes"] is not None and eta["minutes"] >= 0


@pytest.mark.django_db
def test_schedule_fallback_clamps_to_zero_when_overdue(trip, stops):
    trip.start_time = timezone.now() - timedelta(hours=3)  # well past the 40-min baseline
    eta = EtaService.estimate(trip, None, stops)
    assert eta["source"] == "schedule"
    assert eta["seconds"] == 0


@pytest.mark.django_db
def test_unavailable_when_no_gps_no_schedule(trip):
    trip.start_time = None  # no GPS, no timetable anchor, no stops
    eta = EtaService.estimate(trip, None, [])
    assert eta["source"] == "unavailable"
    assert eta["minutes"] is None


@pytest.mark.django_db
def test_unavailable_when_trip_not_in_progress(trip, stops):
    trip.status = TripStatus.COMPLETED
    pos = _gps(trip, "27.701000", "85.301000", "30.00")
    eta = EtaService.estimate(trip, pos, stops)
    assert eta == {"minutes": None, "seconds": None, "next_stop": None, "source": "unavailable"}
