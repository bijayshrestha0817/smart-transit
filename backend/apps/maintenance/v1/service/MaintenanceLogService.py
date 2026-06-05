"""Business logic for maintenance logs. Views call these; these call repositories."""

from django.db import transaction

from apps.maintenance.models import MaintenanceLog
from apps.maintenance.repository import MaintenanceLogRepository


class MaintenanceLogService:
    @staticmethod
    def create(data: dict) -> MaintenanceLog:
        with transaction.atomic():
            return MaintenanceLogRepository.create(data)

    @staticmethod
    def update(instance: MaintenanceLog, data: dict) -> MaintenanceLog:
        with transaction.atomic():
            return MaintenanceLogRepository.apply_update(instance, data)
