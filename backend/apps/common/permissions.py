"""Role-based DRF permission classes.

Every view declares one of these explicitly — no endpoint ships without an
intentional permission. Role strings match ``apps.accounts.models.User.Roles``
values; they're duplicated here as literals to avoid importing the accounts app
at module-import time.
"""

from rest_framework.permissions import BasePermission

ROLE_PASSENGER = "passenger"
ROLE_DRIVER = "driver"
ROLE_ADMIN = "admin"


class _RolePermission(BasePermission):
    required_role: str = ""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == self.required_role)


class IsPassenger(_RolePermission):
    required_role = ROLE_PASSENGER


class IsDriver(_RolePermission):
    required_role = ROLE_DRIVER


class IsAdmin(_RolePermission):
    required_role = ROLE_ADMIN


class IsOwnerOrAdmin(BasePermission):
    """Object-level: admins pass; otherwise the requester must own the object.

    The owning attribute defaults to ``user``; a view can override it by setting
    ``owner_field`` (e.g. ``"passenger"`` on a ticket view).
    """

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role == ROLE_ADMIN:
            return True
        owner = getattr(obj, getattr(view, "owner_field", "user"), None)
        return owner == user
