"""Notification model — the in-app alert feed (er-diagram §4).

Inherits ``TimeStampedSoftDeleteModel`` (timestamps + soft delete). Each row is a
single notification addressed to one ``user`` (the recipient); ``read_at`` is null
while unread. ``payload_json`` carries free-form, type-specific data (e.g.
``{"trip_id": 7, "route_name": "Ring Road"}``). The ``(user, read_at)`` index backs
the unread-feed-per-user query.
"""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedSoftDeleteModel

from .enums import NotificationType


class Notification(TimeStampedSoftDeleteModel):
    """One in-app alert addressed to a single recipient user."""

    Type = NotificationType  # enum lives in enums.py; aliased so Notification.Type.X works

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    payload_json = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "notifications"
        indexes = [
            models.Index(fields=["user", "read_at"]),
        ]

    def __str__(self) -> str:
        return f"Notification #{self.pk} ({self.type}) -> user {self.user_id}"
