"""Business logic for notifications. Views (and the trip signal) call these; these
call the repository. All ``@staticmethod``; mutations run inside ``transaction.atomic()``.

``create`` persists the row, then enqueues async delivery via
``transaction.on_commit`` — NOT at save/post_save time — so a real (non-eager) worker
can never run before the row commits (no read-before-commit race). Under tests
``CELERY_TASK_ALWAYS_EAGER`` makes the enqueued task run inline on commit.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.notifications.enums import NotificationType
from apps.notifications.models import Notification
from apps.notifications.repository import NotificationRepository
from apps.notifications.tasks import deliver_notification

logger = logging.getLogger(__name__)


def _enqueue_delivery(notification_id) -> None:
    """Best-effort enqueue of async delivery. Runs in the ``on_commit`` callback AFTER
    the outermost transaction commits — i.e. outside the signal/service try-contexts —
    so a broker/publish failure here (e.g. Redis down -> ``OperationalError`` from
    ``.delay()``) would otherwise propagate into the request that just committed the
    write. Swallow + log to keep delivery best-effort, matching tasks.py/realtime.py.
    """
    try:
        deliver_notification.delay(notification_id)
    except Exception:  # noqa: BLE001 — enqueue is best-effort; never break the committed write
        logger.warning(
            "failed to enqueue deliver_notification for %s", notification_id, exc_info=True
        )


class NotificationService:
    @staticmethod
    def create(user, type: NotificationType, payload: dict | None = None) -> Notification:
        """Persist a notification (atomic) and enqueue best-effort delivery on commit."""
        with transaction.atomic():
            notification = NotificationRepository.create(
                {"user": user, "type": type, "payload_json": payload or {}}
            )
            # Defer delivery to AFTER the row commits so a real worker never reads
            # before the write lands (the row could still roll back here). The enqueue
            # is guarded (_enqueue_delivery) so a broker outage can't break the request.
            transaction.on_commit(lambda: _enqueue_delivery(notification.id))
        return notification

    @staticmethod
    def feed(user, unread_only: bool = False):
        """Owner-scoped queryset (for cursor pagination); ``unread_only`` → unread rows."""
        queryset = NotificationRepository.for_user(user)
        if unread_only:
            queryset = queryset.filter(read_at__isnull=True)
        return queryset

    @staticmethod
    def mark_read(notification: Notification) -> Notification:
        """Set ``read_at`` once (idempotent — a second call is a no-op)."""
        if notification.read_at is None:
            with transaction.atomic():
                notification.read_at = timezone.now()
                notification.save(update_fields=["read_at", "updated_at"])
        return notification

    @staticmethod
    def mark_all_read(user) -> int:
        """Bulk-mark the user's unread notifications read; returns the count touched."""
        with transaction.atomic():
            return NotificationRepository.mark_all_read(user)
