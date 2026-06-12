"""REST + RBAC tests for the trips API: driver lifecycle, admin CRUD/fleet, passenger active.

Role auth uses ``client.force_authenticate(user=...)``. Body assertions read the rendered
``{data, meta, errors}`` envelope.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.buses.models import Bus, BusStop, Route
from apps.trips.enums import TripStatus
from apps.trips.models import GpsLocation, Trip

User = get_user_model()

PASSWORD = "StrongPass123!"
ADMIN_TRIPS_URL = "/api/v1/admin/trips/"
DRIVER_TRIPS_URL = "/api/v1/driver/trips/"
ACTIVE_URL = "/api/v1/trips/active/"
FLEET_URL = "/api/v1/admin/fleet/"


def eta_url(trip_id) -> str:
    return f"/api/v1/trips/{trip_id}/eta/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        email="admin@example.com", password=PASSWORD, role=User.Roles.ADMIN, is_verified=True
    )


@pytest.fixture
def passenger(db):
    return User.objects.create_user(email="rider@example.com", password=PASSWORD, is_verified=True)


@pytest.fixture
def driver(db):
    return User.objects.create_user(
        email="driver@example.com", password=PASSWORD, role=User.Roles.DRIVER, is_verified=True
    )


@pytest.fixture
def other_driver(db):
    return User.objects.create_user(
        email="driver2@example.com", password=PASSWORD, role=User.Roles.DRIVER, is_verified=True
    )


@pytest.fixture
def route(db):
    return Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)


@pytest.fixture
def bus(db):
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


@pytest.fixture
def trip(route, driver, bus):
    return Trip.objects.create(bus=bus, route=route, driver=driver)


# ── Driver lifecycle ─────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_driver_can_start_and_end_trip(client, driver, trip):
    client.force_authenticate(user=driver)

    start = client.post(f"{DRIVER_TRIPS_URL}{trip.id}/start/", {}, format="json")
    assert start.status_code == 200
    assert start.json()["data"]["status"] == TripStatus.IN_PROGRESS

    end = client.post(f"{DRIVER_TRIPS_URL}{trip.id}/end/", {}, format="json")
    assert end.status_code == 200
    assert end.json()["data"]["status"] == TripStatus.COMPLETED
    trip.refresh_from_db()
    assert trip.status == TripStatus.COMPLETED


@pytest.mark.django_db
def test_driver_restart_returns_409_code(client, driver, trip):
    client.force_authenticate(user=driver)
    client.post(f"{DRIVER_TRIPS_URL}{trip.id}/start/", {}, format="json")
    resp = client.post(f"{DRIVER_TRIPS_URL}{trip.id}/start/", {}, format="json")
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "trip_already_started"


@pytest.mark.django_db
def test_driver_end_not_in_progress_returns_409_code(client, driver, trip):
    client.force_authenticate(user=driver)
    resp = client.post(f"{DRIVER_TRIPS_URL}{trip.id}/end/", {}, format="json")
    assert resp.status_code == 409
    assert resp.json()["errors"][0]["code"] == "trip_not_in_progress"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("post", "start/", {}),
        ("post", "end/", {}),
        ("post", "passenger-count/", {"count": 5}),
        ("post", "gps/batch/", {"points": []}),
        ("get", "", None),  # retrieve
    ],
)
def test_driver_cannot_act_on_other_drivers_trip(client, other_driver, trip, method, suffix, body):
    client.force_authenticate(user=other_driver)
    # Scoped queryset -> 404 (not owned), never leaks the trip, on every detail route.
    url = f"{DRIVER_TRIPS_URL}{trip.id}/{suffix}"
    if method == "get":
        resp = client.get(url)
    else:
        resp = client.post(url, body, format="json")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_driver_can_set_passenger_count(client, driver, trip):
    client.force_authenticate(user=driver)
    resp = client.post(
        f"{DRIVER_TRIPS_URL}{trip.id}/passenger-count/", {"count": 17}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["passenger_count"] == 17
    trip.refresh_from_db()
    assert trip.passenger_count == 17


@pytest.mark.django_db
def test_driver_gps_batch_persists_points_and_returns_202(client, driver, trip):
    client.force_authenticate(user=driver)
    base = timezone.now()
    payload = {
        "points": [
            {
                "lat": "27.700000",
                "lng": "85.300000",
                "speed": "12.50",
                "heading": "90.00",
                "timestamp": (base + timedelta(seconds=offset)).isoformat(),
            }
            for offset in (0, 3, 6)
        ]
    }
    resp = client.post(f"{DRIVER_TRIPS_URL}{trip.id}/gps/batch/", payload, format="json")
    assert resp.status_code == 202
    assert resp.json()["data"]["count"] == 3
    assert GpsLocation.objects.filter(trip=trip).count() == 3


@pytest.mark.django_db
def test_driver_gps_batch_empty_is_noop(client, driver, trip):
    client.force_authenticate(user=driver)
    resp = client.post(f"{DRIVER_TRIPS_URL}{trip.id}/gps/batch/", {"points": []}, format="json")
    assert resp.status_code == 202
    assert resp.json()["data"]["count"] == 0
    assert GpsLocation.objects.filter(trip=trip).count() == 0


@pytest.mark.django_db
def test_driver_can_retrieve_own_trip(client, driver, trip):
    client.force_authenticate(user=driver)
    resp = client.get(f"{DRIVER_TRIPS_URL}{trip.id}/")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == trip.id


@pytest.mark.django_db
def test_driver_list_returns_only_own_trips(client, driver, other_driver, route, bus, trip):
    # A trip owned by another driver must never appear in this driver's list.
    other_trip = Trip.objects.create(bus=bus, route=route, driver=other_driver)
    client.force_authenticate(user=driver)
    resp = client.get(DRIVER_TRIPS_URL)
    assert resp.status_code == 200
    envelope = resp.json()
    assert isinstance(envelope["data"], list)
    assert envelope["meta"]["pagination"]["page_size"] == 20
    ids = {t["id"] for t in envelope["data"]}
    assert trip.id in ids
    assert other_trip.id not in ids


@pytest.mark.django_db
def test_driver_list_filters_by_status(client, driver, route, bus):
    scheduled = Trip.objects.create(bus=bus, route=route, driver=driver)
    in_progress = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS
    )
    client.force_authenticate(user=driver)
    resp = client.get(DRIVER_TRIPS_URL, {"status": TripStatus.IN_PROGRESS})
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()["data"]}
    assert ids == {in_progress.id}
    assert scheduled.id not in ids


@pytest.mark.django_db
def test_driver_list_requires_auth(client):
    assert client.get(DRIVER_TRIPS_URL).status_code == 401


@pytest.mark.django_db
def test_driver_list_forbidden_for_passenger_and_admin(client, passenger, admin):
    client.force_authenticate(user=passenger)
    assert client.get(DRIVER_TRIPS_URL).status_code == 403
    client.force_authenticate(user=admin)
    assert client.get(DRIVER_TRIPS_URL).status_code == 403


# ── RBAC: driver lifecycle is driver-only ────────────────────────────────────
@pytest.mark.django_db
def test_driver_start_requires_auth(client, trip):
    assert client.post(f"{DRIVER_TRIPS_URL}{trip.id}/start/", {}, format="json").status_code == 401


@pytest.mark.django_db
def test_driver_start_forbidden_for_passenger_and_admin(client, passenger, admin, trip):
    client.force_authenticate(user=passenger)
    assert client.post(f"{DRIVER_TRIPS_URL}{trip.id}/start/", {}, format="json").status_code == 403
    client.force_authenticate(user=admin)
    assert client.post(f"{DRIVER_TRIPS_URL}{trip.id}/start/", {}, format="json").status_code == 403


# ── Admin trip CRUD ──────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_admin_can_create_and_list_trips(client, admin, route, bus, driver):
    client.force_authenticate(user=admin)
    create = client.post(
        ADMIN_TRIPS_URL,
        {"bus": bus.id, "route": route.id, "driver": driver.id},
        format="json",
    )
    assert create.status_code == 201
    body = create.json()["data"]
    assert body["status"] == TripStatus.SCHEDULED
    assert body["bus_plate"] == bus.plate
    assert body["driver_email"] == driver.email

    listing = client.get(ADMIN_TRIPS_URL)
    assert listing.status_code == 200
    envelope = listing.json()
    assert isinstance(envelope["data"], list)
    assert envelope["meta"]["pagination"]["page_size"] == 20
    assert any(t["id"] == body["id"] for t in envelope["data"])


@pytest.mark.django_db
def test_admin_create_rejects_non_driver(client, admin, route, bus, passenger):
    client.force_authenticate(user=admin)
    resp = client.post(
        ADMIN_TRIPS_URL,
        {"bus": bus.id, "route": route.id, "driver": passenger.id},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "invalid_driver"


@pytest.mark.django_db
def test_admin_can_soft_delete_trip(client, admin, trip):
    client.force_authenticate(user=admin)
    assert client.delete(f"{ADMIN_TRIPS_URL}{trip.id}/").status_code == 204
    assert not Trip.objects.filter(id=trip.id).exists()
    assert Trip.all_objects.get(id=trip.id).is_deleted is True


@pytest.mark.django_db
def test_admin_trips_forbidden_for_passenger(client, passenger):
    client.force_authenticate(user=passenger)
    assert client.get(ADMIN_TRIPS_URL).status_code == 403


@pytest.mark.django_db
def test_admin_trips_requires_auth(client):
    assert client.get(ADMIN_TRIPS_URL).status_code == 401


# ── Passenger active trips ───────────────────────────────────────────────────
@pytest.mark.django_db
def test_passenger_active_trips_returns_trips_and_position(client, passenger, route, bus, driver):
    base = timezone.now()
    trip = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    GpsLocation.objects.create(
        trip=trip,
        lat=Decimal("27.700000"),
        lng=Decimal("85.300000"),
        speed=Decimal("11.00"),
        timestamp=base,
    )
    client.force_authenticate(user=passenger)
    resp = client.get(ACTIVE_URL, {"route": route.id})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["trip"]["id"] == trip.id
    assert data[0]["last_position"]["lat"] == "27.700000"


@pytest.mark.django_db
def test_passenger_active_trips_requires_route_param(client, passenger):
    client.force_authenticate(user=passenger)
    resp = client.get(ACTIVE_URL)
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["field"] == "route"


@pytest.mark.django_db
def test_passenger_active_forbidden_for_driver(client, driver):
    client.force_authenticate(user=driver)
    assert client.get(ACTIVE_URL, {"route": 1}).status_code == 403


@pytest.mark.django_db
def test_passenger_active_requires_auth(client):
    assert client.get(ACTIVE_URL, {"route": 1}).status_code == 401


# ── Admin fleet snapshot ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_admin_fleet_snapshot(client, admin, route, bus, driver):
    base = timezone.now()
    trip = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    GpsLocation.objects.create(
        trip=trip,
        lat=Decimal("27.710000"),
        lng=Decimal("85.310000"),
        speed=Decimal("9.00"),
        timestamp=base,
    )
    client.force_authenticate(user=admin)
    resp = client.get(FLEET_URL)
    assert resp.status_code == 200
    envelope = resp.json()
    assert envelope["errors"] is None
    assert "data" in envelope and "meta" in envelope and "errors" in envelope
    assert len(envelope["data"]) == 1
    assert envelope["data"][0]["trip"]["id"] == trip.id


@pytest.mark.django_db
def test_admin_fleet_forbidden_for_passenger(client, passenger):
    client.force_authenticate(user=passenger)
    assert client.get(FLEET_URL).status_code == 403


# ── Baseline ETA ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_active_trips_payload_includes_eta(client, passenger, route, bus, driver):
    base = timezone.now()
    trip = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    GpsLocation.objects.create(
        trip=trip,
        lat=Decimal("27.700000"),
        lng=Decimal("85.300000"),
        speed=Decimal("20.00"),
        timestamp=base,
    )
    client.force_authenticate(user=passenger)
    resp = client.get(ACTIVE_URL, {"route": route.id})
    assert resp.status_code == 200
    eta = resp.json()["data"][0]["eta"]
    # No GPS-anchored stops here, but a running trip with a baseline duration → schedule.
    assert eta["source"] in {"gps", "schedule", "unavailable"}
    assert eta["source"] == "schedule"


@pytest.mark.django_db
def test_trip_eta_endpoint_gps_estimate(client, passenger, route, bus, driver):
    base = timezone.now()
    BusStop.objects.create(
        route=route,
        name="Koteshwor",
        lat=Decimal("27.700000"),
        lng=Decimal("85.300000"),
        sequence=1,
    )
    BusStop.objects.create(
        route=route, name="Tinkune", lat=Decimal("27.720000"), lng=Decimal("85.320000"), sequence=2
    )
    trip = Trip.objects.create(
        bus=bus, route=route, driver=driver, status=TripStatus.IN_PROGRESS, start_time=base
    )
    GpsLocation.objects.create(
        trip=trip,
        lat=Decimal("27.701000"),
        lng=Decimal("85.301000"),
        speed=Decimal("30.00"),
        timestamp=base,
    )
    client.force_authenticate(user=passenger)
    resp = client.get(eta_url(trip.id))
    assert resp.status_code == 200
    eta = resp.json()["data"]
    assert eta["source"] == "gps"
    assert eta["next_stop"] == "Tinkune"
    assert eta["minutes"] is not None


@pytest.mark.django_db
def test_trip_eta_unavailable_for_scheduled_trip(client, passenger, trip):
    # The trip exists but hasn't started (no start_time, not in progress) → 200 unavailable,
    # NOT a 404. The trip is real; the estimate just isn't.
    client.force_authenticate(user=passenger)
    resp = client.get(eta_url(trip.id))
    assert resp.status_code == 200
    assert resp.json()["data"]["source"] == "unavailable"


@pytest.mark.django_db
def test_trip_eta_404_for_unknown_trip(client, passenger):
    client.force_authenticate(user=passenger)
    resp = client.get(eta_url(999999))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_trip_eta_forbidden_for_driver(client, driver, trip):
    client.force_authenticate(user=driver)
    assert client.get(eta_url(trip.id)).status_code == 403


@pytest.mark.django_db
def test_trip_eta_requires_auth(client, trip):
    assert client.get(eta_url(trip.id)).status_code == 401
