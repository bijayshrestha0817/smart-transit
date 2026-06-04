"""Data access for Notification. All Notification ORM lives here."""

from django.utils import timezone

from apps.common.repository import BaseRepository
from apps.notifications.models import Notification


class NotificationRepository(BaseRepository):
    model = Notification

    @classmethod
    def active(cls):
        return Notification.objects.all()

    @classmethod
    def for_user(cls, user):
        """The user's active notifications, newest first."""
        return cls.active().filter(user=user).order_by("-created_at")

    @classmethod
    def get_for_user(cls, notification_id, user):
        """A single notification owned by ``user`` (owner-scoped — no IDOR)."""
        return cls.for_user(user).filter(id=notification_id).first()

    @classmethod
    def create(cls, data: dict) -> Notification:
        return Notification.objects.create(**data)

    @classmethod
    def exists_for_trip(cls, user, notification_type, trip_id) -> bool:
        """Idempotency guard for the trip-completed signal (active rows only)."""
        return (
            cls.for_user(user)
            .filter(type=notification_type, payload_json__trip_id=trip_id)
            .exists()
        )

    @classmethod
    def mark_all_read(cls, user) -> int:
        """Bulk-mark the user's unread notifications read; returns the count touched."""
        return cls.for_user(user).filter(read_at__isnull=True).update(read_at=timezone.now())
