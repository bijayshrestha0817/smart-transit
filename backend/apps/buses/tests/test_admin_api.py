"""Admin CRUD + RBAC: buses, routes/stops, drivers, and the extra actions.

Role auth uses ``client.force_authenticate(user=...)`` (DRF supports it even with
the cookie-JWT default). Body assertions read the rendered envelope.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.buses.models import Bus, BusStop, Route

User = get_user_model()

BUSES_URL = "/api/v1/admin/buses/"
ROUTES_URL = "/api/v1/admin/routes/"
DRIVERS_URL = "/api/v1/admin/drivers/"
PASSWORD = "StrongPass123!"


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
def route(db):
    return Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)


# ── RBAC ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_admin_buses_requires_auth(client):
    assert client.get(BUSES_URL).status_code == 401
    assert client.post(BUSES_URL, {}, format="json").status_code == 401


@pytest.mark.django_db
def test_admin_buses_forbidden_for_passenger(client, passenger):
    client.force_authenticate(user=passenger)
    assert client.get(BUSES_URL).status_code == 403
    assert client.post(BUSES_URL, {"plate": "X", "capacity": 1}, format="json").status_code == 403


# ── Bus CRUD ─────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_admin_can_crud_bus(client, admin):
    client.force_authenticate(user=admin)

    # Create
    resp = client.post(BUSES_URL, {"plate": "BA 1 KHA 1001", "capacity": 42}, format="json")
    assert resp.status_code == 201
    bus_id = resp.json()["data"]["id"]

    # List + retrieve
    assert any(b["id"] == bus_id for b in client.get(BUSES_URL).json()["data"])
    assert client.get(f"{BUSES_URL}{bus_id}/").json()["data"]["plate"] == "BA 1 KHA 1001"

    # Patch
    patch = client.patch(f"{BUSES_URL}{bus_id}/", {"capacity": 50}, format="json")
    assert patch.status_code == 200
    assert Bus.objects.get(id=bus_id).capacity == 50

    # Soft delete
    assert client.delete(f"{BUSES_URL}{bus_id}/").status_code == 204
    assert not any(b["id"] == bus_id for b in client.get(BUSES_URL).json()["data"])
    tombstone = Bus.all_objects.get(id=bus_id)
    assert tombstone.is_deleted is True


@pytest.mark.django_db
def test_admin_create_rejects_duplicate_plate(client, admin):
    client.force_authenticate(user=admin)
    Bus.objects.create(plate="DUP 1", capacity=10)
    resp = client.post(BUSES_URL, {"plate": "DUP 1", "capacity": 10}, format="json")
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "duplicate_plate"


# ── Bus actions ──────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_assign_driver_with_valid_driver(client, admin, driver):
    client.force_authenticate(user=admin)
    bus = Bus.objects.create(plate="BA 2 KHA 2002", capacity=30)
    resp = client.patch(
        f"{BUSES_URL}{bus.id}/assign-driver/", {"driver_id": driver.id}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["assigned_driver"] == driver.id
    bus.refresh_from_db()
    assert bus.assigned_driver_id == driver.id


@pytest.mark.django_db
def test_assign_driver_rejects_non_driver(client, admin, passenger):
    client.force_authenticate(user=admin)
    bus = Bus.objects.create(plate="BA 3 KHA 3003", capacity=30)
    resp = client.patch(
        f"{BUSES_URL}{bus.id}/assign-driver/", {"driver_id": passenger.id}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "invalid_driver"


@pytest.mark.django_db
def test_maintenance_action_sets_status(client, admin):
    client.force_authenticate(user=admin)
    bus = Bus.objects.create(plate="BA 4 KHA 4004", capacity=30, status=Bus.Status.ACTIVE)
    resp = client.patch(f"{BUSES_URL}{bus.id}/maintenance/", {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == Bus.Status.MAINTENANCE
    bus.refresh_from_db()
    assert bus.status == Bus.Status.MAINTENANCE


# ── Route stops action ───────────────────────────────────────────────────────
@pytest.mark.django_db
def test_assign_stops_replaces_route_stops(client, admin, route):
    client.force_authenticate(user=admin)
    # Pre-existing stop that should be replaced.
    BusStop.objects.create(name="Old", lat="27.70", lng="85.30", route=route, sequence=1)
    payload = {
        "stops": [
            {"name": "Koteshwor", "lat": "27.6789", "lng": "85.3478", "sequence": 1},
            {"name": "Tinkune", "lat": "27.6853", "lng": "85.3489", "sequence": 2},
        ]
    }
    resp = client.post(f"{ROUTES_URL}{route.id}/stops/", payload, format="json")
    assert resp.status_code == 201
    assert len(resp.json()["data"]) == 2

    active = list(route.stops.all().order_by("sequence"))
    assert [s.name for s in active] == ["Koteshwor", "Tinkune"]
    # The old stop is now a tombstone, not active.
    assert not route.stops.filter(name="Old").exists()


# ── Driver management ────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_admin_can_create_driver(client, admin):
    client.force_authenticate(user=admin)
    resp = client.post(
        DRIVERS_URL,
        {"email": "newdriver@example.com", "password": PASSWORD, "full_name": "New Driver"},
        format="json",
    )
    assert resp.status_code == 201
    created = User.objects.get(email="newdriver@example.com")
    assert created.role == User.Roles.DRIVER
    assert created.is_verified is True


@pytest.mark.django_db
def test_driver_list_excludes_non_drivers(client, admin, driver, passenger):
    client.force_authenticate(user=admin)
    emails = {d["email"] for d in client.get(DRIVERS_URL).json()["data"]}
    assert "driver@example.com" in emails
    assert "rider@example.com" not in emails
    assert "admin@example.com" not in emails
