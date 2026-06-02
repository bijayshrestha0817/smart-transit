"""Model-level tests: soft delete, partial-unique reuse, and active uniqueness."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.buses.models import Bus, BusStop, Route


@pytest.fixture
def route(db) -> Route:
    return Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)


@pytest.mark.django_db
def test_soft_delete_hides_from_default_manager(route):
    bus = Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)
    bus.delete()  # soft delete

    assert not Bus.objects.filter(pk=bus.pk).exists()  # hidden from default
    tombstone = Bus.all_objects.get(pk=bus.pk)  # still present via escape hatch
    assert tombstone.is_deleted is True


@pytest.mark.django_db
def test_plate_reusable_after_soft_delete(route):
    bus = Bus.objects.create(plate="BA 9 KHA 9999", capacity=30)
    bus.delete()

    # The partial-unique constraint ignores tombstones, so the plate is free again.
    revived = Bus.objects.create(plate="BA 9 KHA 9999", capacity=30)
    assert revived.pk != bus.pk
    assert Bus.objects.filter(plate="BA 9 KHA 9999").count() == 1


@pytest.mark.django_db
def test_duplicate_active_plate_rejected():
    Bus.objects.create(plate="BA 5 KHA 5555", capacity=30)
    with pytest.raises(IntegrityError), transaction.atomic():
        Bus.objects.create(plate="BA 5 KHA 5555", capacity=30)


@pytest.mark.django_db
def test_two_active_stops_cannot_share_sequence(route):
    BusStop.objects.create(
        name="A", lat=Decimal("27.7"), lng=Decimal("85.3"), route=route, sequence=1
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        BusStop.objects.create(
            name="B", lat=Decimal("27.71"), lng=Decimal("85.31"), route=route, sequence=1
        )


@pytest.mark.django_db
def test_soft_deleted_stop_frees_its_sequence(route):
    stop = BusStop.objects.create(
        name="A", lat=Decimal("27.7"), lng=Decimal("85.3"), route=route, sequence=1
    )
    stop.delete()
    # Same (route, sequence) is reusable once the old one is a tombstone.
    revived = BusStop.objects.create(
        name="A2", lat=Decimal("27.7"), lng=Decimal("85.3"), route=route, sequence=1
    )
    assert revived.pk != stop.pk


@pytest.mark.django_db
def test_route_str_returns_name(route):
    assert str(route) == "Ring Road"
