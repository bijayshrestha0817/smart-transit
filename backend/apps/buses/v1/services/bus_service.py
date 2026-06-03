"""Business logic for buses. Views call these; these call repositories."""

from django.db import transaction

from apps.buses.models import Bus
from apps.buses.repository import BusRepository, DriverRepository
from apps.common.exceptions import CustomException


class BusService:
    @staticmethod
    def create(data: dict) -> Bus:
        with transaction.atomic():
            return BusRepository.create(data)

    @staticmethod
    def update(bus: Bus, data: dict) -> Bus:
        with transaction.atomic():
            return BusRepository.apply_update(bus, data)

    @staticmethod
    def assign_driver(bus: Bus, driver_id: int) -> Bus:
        driver = DriverRepository.get_driver(driver_id)
        if driver is None:
            raise CustomException(
                message="No active driver with this id.", status=404, code="invalid_driver"
            )
        with transaction.atomic():
            bus.assigned_driver = driver
            bus.save(update_fields=["assigned_driver", "updated_at"])
        return bus

    @staticmethod
    def set_maintenance(bus: Bus) -> Bus:
        with transaction.atomic():
            bus.status = Bus.Status.MAINTENANCE
            bus.save(update_fields=["status", "updated_at"])
        return bus
