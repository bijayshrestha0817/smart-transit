"""Admin maintenance-log CRUD + RBAC + validation.

Role auth uses ``client.force_authenticate(user=...)`` (DRF supports it even with the
cookie-JWT default). Body assertions read the rendered ``{data, meta, errors}`` envelope.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.buses.models import Bus
from apps.maintenance.models import MaintenanceLog

User = get_user_model()

LOGS_URL = "/api/v1/admin/maintenance-logs/"
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
def bus(db) -> Bus:
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


def _payload(bus: Bus) -> dict:
    return {
        "bus": bus.id,
        "service_type": "Oil change",
        "cost": "1200.50",
        "serviced_at": timezone.now().isoformat(),
        "next_due": date(2026, 12, 1).isoformat(),
    }


# ── RBAC ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_requires_auth(client):
    assert client.get(LOGS_URL).status_code == 401
    assert client.post(LOGS_URL, {}, format="json").status_code == 401


@pytest.mark.django_db
def test_forbidden_for_passenger(client, passenger):
    client.force_authenticate(user=passenger)
    assert client.get(LOGS_URL).status_code == 403
    assert client.post(LOGS_URL, {}, format="json").status_code == 403


@pytest.mark.django_db
def test_forbidden_for_driver(client, driver):
    client.force_authenticate(user=driver)
    assert client.get(LOGS_URL).status_code == 403
    assert client.post(LOGS_URL, {}, format="json").status_code == 403


# ── CRUD ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_admin_can_crud_maintenance_log(client, admin, bus):
    client.force_authenticate(user=admin)

    # Create
    resp = client.post(LOGS_URL, _payload(bus), format="json")
    assert resp.status_code == 201
    log_id = resp.json()["data"]["id"]

    # List contains it
    assert any(item["id"] == log_id for item in client.get(LOGS_URL).json()["data"])

    # Detail returns bus_plate + cost as a string
    detail = client.get(f"{LOGS_URL}{log_id}/").json()["data"]
    assert detail["bus_plate"] == "BA 1 KHA 1001"
    assert detail["cost"] == "1200.50"

    # Patch cost
    patch = client.patch(f"{LOGS_URL}{log_id}/", {"cost": "999.99"}, format="json")
    assert patch.status_code == 200
    assert MaintenanceLog.objects.get(id=log_id).cost == Decimal("999.99")

    # Soft delete
    assert client.delete(f"{LOGS_URL}{log_id}/").status_code == 204
    assert not any(item["id"] == log_id for item in client.get(LOGS_URL).json()["data"])
    tombstone = MaintenanceLog.all_objects.get(id=log_id)
    assert tombstone.is_deleted is True


# ── Validation ───────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_invalid_bus_rejected(client, admin):
    client.force_authenticate(user=admin)
    payload = {
        "bus": 999999,
        "service_type": "Oil change",
        "cost": "100.00",
        "serviced_at": timezone.now().isoformat(),
    }
    resp = client.post(LOGS_URL, payload, format="json")
    assert resp.status_code == 400
    # The ``bus`` PK field rejects an unknown id with DRF's ``does_not_exist`` before
    # ``validate_bus`` runs — same contract as AdminTripWriteSerializer's bus/route.
    assert resp.json()["errors"][0]["code"] == "does_not_exist"
    assert resp.json()["errors"][0]["field"] == "bus"


@pytest.mark.django_db
def test_negative_cost_rejected(client, admin, bus):
    client.force_authenticate(user=admin)
    payload = _payload(bus)
    payload["cost"] = "-1.00"
    resp = client.post(LOGS_URL, payload, format="json")
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "min_value"


@pytest.mark.django_db
def test_create_with_next_due_omitted(client, admin, bus):
    # next_due is optional at the API/serializer boundary (not just the model): a payload
    # that omits it must still 201, and the read response serializes it as null.
    client.force_authenticate(user=admin)
    payload = _payload(bus)
    payload.pop("next_due")
    resp = client.post(LOGS_URL, payload, format="json")
    assert resp.status_code == 201
    assert resp.json()["data"]["next_due"] is None


# ── Filtering & ordering ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_filter_by_bus(client, admin):
    # filterset_fields = ["bus"] — the per-bus filter that backs the (bus, -serviced_at)
    # index. With one log per bus, ?bus=<id> must return only that bus's log.
    client.force_authenticate(user=admin)
    bus_a = Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)
    bus_b = Bus.objects.create(plate="BA 2 KHA 2002", capacity=40)
    log_a = MaintenanceLog.objects.create(
        bus=bus_a, service_type="A", cost=Decimal("100.00"), serviced_at=timezone.now()
    )
    log_b = MaintenanceLog.objects.create(
        bus=bus_b, service_type="B", cost=Decimal("200.00"), serviced_at=timezone.now()
    )
    ids = [item["id"] for item in client.get(f"{LOGS_URL}?bus={bus_a.id}").json()["data"]]
    assert ids == [log_a.id]
    assert log_b.id not in ids


@pytest.mark.django_db
def test_ordering_by_serviced_at(client, admin, bus):
    # ordering_fields includes "serviced_at"; OrderingFilter is in DEFAULT_FILTER_BACKENDS.
    # Asc vs desc must flip the data order, locking the declared ordering contract.
    client.force_authenticate(user=admin)
    older = MaintenanceLog.objects.create(
        bus=bus,
        service_type="Older",
        cost=Decimal("100.00"),
        serviced_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    newer = MaintenanceLog.objects.create(
        bus=bus,
        service_type="Newer",
        cost=Decimal("200.00"),
        serviced_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    asc = [item["id"] for item in client.get(f"{LOGS_URL}?ordering=serviced_at").json()["data"]]
    desc = [item["id"] for item in client.get(f"{LOGS_URL}?ordering=-serviced_at").json()["data"]]
    assert asc == [older.id, newer.id]
    assert desc == [newer.id, older.id]


@pytest.mark.django_db
def test_ordering_by_cost(client, admin, bus):
    # ordering_fields includes "cost" — same flip contract on the money column.
    client.force_authenticate(user=admin)
    cheap = MaintenanceLog.objects.create(
        bus=bus, service_type="Cheap", cost=Decimal("100.00"), serviced_at=timezone.now()
    )
    pricey = MaintenanceLog.objects.create(
        bus=bus, service_type="Pricey", cost=Decimal("900.00"), serviced_at=timezone.now()
    )
    asc = [item["id"] for item in client.get(f"{LOGS_URL}?ordering=cost").json()["data"]]
    desc = [item["id"] for item in client.get(f"{LOGS_URL}?ordering=-cost").json()["data"]]
    assert asc == [cheap.id, pricey.id]
    assert desc == [pricey.id, cheap.id]


# ── Envelope ─────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_list_is_enveloped_and_paginated(client, admin, bus):
    client.force_authenticate(user=admin)
    MaintenanceLog.objects.create(
        bus=bus, service_type="Inspection", cost=Decimal("250.00"), serviced_at=timezone.now()
    )
    body = client.get(LOGS_URL).json()
    assert isinstance(body["data"], list)
    assert body["meta"]["pagination"]["page_size"] == 20
    assert body["errors"] is None
