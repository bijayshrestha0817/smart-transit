"""Data access for MaintenanceLog. All MaintenanceLog ORM lives here."""

from apps.common.repository import BaseRepository
from apps.maintenance.models import MaintenanceLog


class MaintenanceLogRepository(BaseRepository):
    model = MaintenanceLog

    @classmethod
    def active(cls):
        # bus_plate is read on every log response (source="bus.plate") — select it
        # up front so the read serializer never triggers an N+1.
        return MaintenanceLog.objects.select_related("bus")

    @classmethod
    def get_by_id(cls, log_id):
        return cls.active().filter(id=log_id).first()

    @classmethod
    def for_bus(cls, bus_id):
        return cls.active().filter(bus_id=bus_id)

    @classmethod
    def create(cls, data: dict) -> MaintenanceLog:
        return MaintenanceLog.objects.create(**data)
