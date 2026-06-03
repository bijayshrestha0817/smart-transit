"""Business logic for driver-account management (role=driver users)."""

from django.db import transaction

from apps.buses.repository import DriverRepository


class DriverService:
    @staticmethod
    def create_driver(data: dict):
        with transaction.atomic():
            return DriverRepository.create_driver(data)

    @staticmethod
    def update_driver(driver, data: dict):
        # password (if present) must go through set_password, not a plain setattr.
        password = data.pop("password", None)
        with transaction.atomic():
            for field, value in data.items():
                setattr(driver, field, value)
            if password:
                driver.set_password(password)
            driver.save()
        return driver
