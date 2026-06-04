"""Data access for DriverLog. All DriverLog ORM lives here."""

from django.contrib.auth import get_user_model

from apps.common.repository import BaseRepository
from apps.driver_logs.models import DriverLog

User = get_user_model()


class DriverLogRepository(BaseRepository):
    model = DriverLog

    @classmethod
    def active(cls):
        # driver/trip are read on every log response — select them up front.
        return DriverLog.objects.select_related("driver", "trip")

    @classmethod
    def create(cls, data: dict) -> DriverLog:
        return DriverLog.objects.create(**data)

    @classmethod
    def for_driver(cls, driver):
        """A driver's own logs, newest event first."""
        return cls.active().filter(driver=driver).order_by("-timestamp")

    @classmethod
    def admins(cls):
        """Active admins — the recipients for an SOS EMERGENCY notification.

        Excludes soft-deleted/deactivated accounts (a soft-deleted user is also
        ``is_active=False``), so a degraded account never receives the alert.
        """
        return User.objects.filter(role="admin", is_active=True, is_deleted=False)
