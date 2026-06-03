"""Data access for drivers (accounts.User rows with role=driver).

The buses app owns the driver-admin endpoints, so the driver ORM lives here for now;
it can move to an accounts repository when accounts is layered (Phase C).
"""

from django.contrib.auth import get_user_model

from apps.common.repository import BaseRepository

User = get_user_model()


class DriverRepository(BaseRepository):
    model = User

    @classmethod
    def active_drivers(cls):
        # User.objects (UserManager) does NOT hide soft-deleted rows — filter explicitly.
        return User.objects.filter(role=User.Roles.DRIVER, is_deleted=False)

    @classmethod
    def get_driver(cls, driver_id):
        return cls.active_drivers().filter(id=driver_id).first()

    @classmethod
    def driver_exists(cls, driver_id) -> bool:
        return cls.active_drivers().filter(id=driver_id).exists()

    @classmethod
    def email_exists(cls, email: str, *, exclude_pk=None) -> bool:
        qs = User.objects.filter(email=email)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    @classmethod
    def create_driver(cls, data: dict):
        # Admin-created drivers are verified immediately (no email gate).
        return User.objects.create_user(role=User.Roles.DRIVER, is_verified=True, **data)
