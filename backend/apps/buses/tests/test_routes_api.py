"""Public route endpoints: enveloped pagination, search, and ordered detail.

Body assertions read ``resp.json()`` (the rendered ``{data, meta, errors}``
envelope), matching the auth test style.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.buses.models import BusStop, Route

ROUTES_URL = "/api/v1/routes/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def routes(db) -> list[Route]:
    ring = Route.objects.create(
        name="Ring Road",
        color="#1E88E5",
        estimated_duration=55,
        fare=Decimal("35.00"),
        polyline_json=[[27.7, 85.3]],
    )
    lagan = Route.objects.create(
        name="Lagankhel–Ratnapark", color="#E53935", estimated_duration=35, fare=Decimal("20.00")
    )
    # Stops created out of order to prove the API returns them by sequence.
    BusStop.objects.create(
        name="Kalanki", lat=Decimal("27.6936"), lng=Decimal("85.2811"), route=ring, sequence=3
    )
    BusStop.objects.create(
        name="Koteshwor", lat=Decimal("27.6789"), lng=Decimal("85.3478"), route=ring, sequence=1
    )
    BusStop.objects.create(
        name="Tinkune", lat=Decimal("27.6853"), lng=Decimal("85.3489"), route=ring, sequence=2
    )
    return [ring, lagan]


@pytest.mark.django_db
def test_route_list_is_public_and_enveloped(client, routes):
    resp = client.get(ROUTES_URL)
    assert resp.status_code == 200  # AllowAny — works unauthenticated
    body = resp.json()
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 2
    assert body["meta"]["pagination"]["page_size"] == 20
    assert body["errors"] is None


@pytest.mark.django_db
def test_route_list_search_filters(client, routes):
    resp = client.get(ROUTES_URL, {"search": "Ring"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Ring Road"


@pytest.mark.django_db
def test_route_list_serializes_fare_as_decimal_string(client, routes):
    resp = client.get(ROUTES_URL)
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Find by name — never assume list ordering.
    ring_row = next(row for row in data if row["name"] == "Ring Road")
    # Guards COERCE_DECIMAL_TO_STRING: the fare crosses the wire as a STRING, not a float.
    assert ring_row["fare"] == "35.00"


@pytest.mark.django_db
def test_route_detail_returns_ordered_stops_and_polyline(client, routes):
    ring = routes[0]
    resp = client.get(f"{ROUTES_URL}{ring.id}/")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fare"] == "35.00"
    assert data["polyline_json"] == [[27.7, 85.3]]
    sequences = [s["sequence"] for s in data["stops"]]
    assert sequences == [1, 2, 3]  # ordered by sequence
    assert [s["name"] for s in data["stops"]] == ["Koteshwor", "Tinkune", "Kalanki"]
