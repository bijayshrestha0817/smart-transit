"""Model-level tests: field persistence, soft delete, and the service-history index."""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.buses.models import Bus
from apps.maintenance.models import MaintenanceLog


@pytest.fixture
def bus(db) -> Bus:
    return Bus.objects.create(plate="BA 1 KHA 1001", capacity=40)


@pytest.mark.django_db
def test_fields_persist(bus):
    serviced_at = timezone.now()
    log = MaintenanceLog.objects.create(
        bus=bus,
        service_type="Oil change",
        cost=Decimal("1200.50"),
        serviced_at=serviced_at,
        next_due=date(2026, 12, 1),
    )
    log.refresh_from_db()
    assert log.bus_id == bus.id
    assert log.service_type == "Oil change"
    assert log.cost == Decimal("1200.50")
    assert log.serviced_at == serviced_at
    assert log.next_due == date(2026, 12, 1)


@pytest.mark.django_db
def test_soft_delete_hides_from_default_manager(bus):
    log = MaintenanceLog.objects.create(
        bus=bus, service_type="Brake check", cost=Decimal("500.00"), serviced_at=timezone.now()
    )
    log.delete()  # soft delete

    assert not MaintenanceLog.objects.filter(pk=log.pk).exists()  # hidden from default
    tombstone = MaintenanceLog.all_objects.get(pk=log.pk)  # still present via escape hatch
    assert tombstone.is_deleted is True


@pytest.mark.django_db
def test_next_due_is_optional(bus):
    log = MaintenanceLog.objects.create(
        bus=bus, service_type="Tyre rotation", cost=Decimal("0"), serviced_at=timezone.now()
    )
    assert log.next_due is None


@pytest.mark.django_db
def test_bus_serviced_at_index_declared():
    index_fields = [tuple(idx.fields) for idx in MaintenanceLog._meta.indexes]
    assert ("bus", "-serviced_at") in index_fields
