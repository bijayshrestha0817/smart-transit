"""Data access for Bus. All Bus ORM lives here."""

from apps.buses.models import Bus
from apps.common.repository import BaseRepository


class BusRepository(BaseRepository):
    model = Bus

    @classmethod
    def active(cls):
        # assigned_driver is shown via BusSerializer.assigned_driver_email — select it.
        return Bus.objects.select_related("assigned_driver")

    @classmethod
    def get_by_id(cls, bus_id):
        return cls.active().filter(id=bus_id).first()

    @classmethod
    def create(cls, data: dict) -> Bus:
        return Bus.objects.create(**data)

    @classmethod
    def plate_exists(cls, plate: str, *, exclude_pk=None) -> bool:
        # Bus.objects excludes soft-deleted rows, matching the partial-unique
        # constraint (WHERE is_deleted = false).
        qs = Bus.objects.filter(plate=plate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()
