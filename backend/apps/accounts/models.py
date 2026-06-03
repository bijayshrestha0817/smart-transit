"""Custom user model.

Email is the login identifier (no username). ``role`` drives RBAC across the
whole API. The timestamp + soft-delete fields mirror ``TimeStampedSoftDeleteModel``
but are declared here directly because the user model needs ``UserManager`` as its
default manager (for ``createsuperuser``). Soft-deleting a user also sets
``is_active=False`` so they can no longer authenticate.
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .enums import UserRole
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    Roles = UserRole  # enum lives in enums.py; aliased so User.Roles.X keeps working

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=16, choices=Roles.choices, default=Roles.PASSENGER)
    is_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []  # email + password are the only required fields

    class Meta:
        db_table = "users"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["role"])]

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"

    def delete(self, using=None, keep_parents=False):
        """Soft delete + deactivate so the account can no longer log in."""
        self.is_deleted = True
        self.is_active = False
        self.save(using=using, update_fields=["is_deleted", "is_active", "updated_at"])

    @property
    def is_passenger(self) -> bool:
        return self.role == self.Roles.PASSENGER

    @property
    def is_driver(self) -> bool:
        return self.role == self.Roles.DRIVER

    @property
    def is_admin(self) -> bool:
        return self.role == self.Roles.ADMIN
