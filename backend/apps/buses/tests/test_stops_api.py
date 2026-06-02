"""Public stop endpoints: listing, route filtering, and `?near=` geo search."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.buses.models import BusStop, Route

STOPS_URL = "/api/v1/stops/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def data(db):
    ring = Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)
    other = Route.objects.create(name="Other", color="#000000", estimated_duration=20)
    near = BusStop.objects.create(
        name="Koteshwor", lat=Decimal("27.7000"), lng=Decimal("85.3000"), route=ring, sequence=1
    )
    far = BusStop.objects.create(
        name="Bhaktapur", lat=Decimal("27.6710"), lng=Decimal("85.4285"), route=ring, sequence=2
    )
    other_stop = BusStop.objects.create(
        name="Lagankhel", lat=Decimal("27.6671"), lng=Decimal("85.3239"), route=other, sequence=1
    )
    return {"ring": ring, "other": other, "near": near, "far": far, "other_stop": other_stop}


@pytest.mark.django_db
def test_stop_list_is_public(client, data):
    resp = client.get(STOPS_URL)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3


@pytest.mark.django_db
def test_stop_list_filters_by_route(client, data):
    resp = client.get(STOPS_URL, {"route": data["other"].id})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert len(body) == 1
    assert body[0]["name"] == "Lagankhel"


@pytest.mark.django_db
def test_stop_list_near_returns_only_nearby(client, data):
    # ~2 km box around Koteshwor includes only the near stop, not Bhaktapur (~13 km).
    resp = client.get(STOPS_URL, {"near": "27.7,85.3", "radius": "2"})
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()["data"]}
    assert "Koteshwor" in names
    assert "Bhaktapur" not in names


@pytest.mark.django_db
def test_stop_list_malformed_near_is_400(client, data):
    resp = client.get(STOPS_URL, {"near": "not-coords"})
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["code"] == "invalid_near"


@pytest.mark.django_db
def test_stop_detail_is_public(client, data):
    resp = client.get(f"{STOPS_URL}{data['near'].id}/")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Koteshwor"
