"""Celery tasks for the notifications app — the platform's first async task.

``deliver_notification`` is enqueued by ``NotificationService.create`` via
``transaction.on_commit`` (so a real worker never runs before the row commits).
Auto-discovered by ``config.celery`` (it scans every app's ``tasks.py``). Under tests
``CELERY_TASK_ALWAYS_EAGER`` runs it inline so delivery is asserted end-to-end.
"""

import logging

from celery import shared_task

from .models import Notification
from .realtime import push_notification

logger = logging.getLogger(__name__)


@shared_task
def deliver_notification(notification_id) -> None:
    """Deliver a persisted notification: best-effort WS broadcast + (future) push/email.

    Loads the row (no-op if it's gone — soft-deleted or never committed), broadcasts to
    the recipient's ``notifications.<user_id>`` group, and logs an FCM/email TODO. Never
    raises hard: a delivery failure must not poison the worker or retry storm.
    """
    try:
        notification = Notification.objects.filter(id=notification_id).first()
        if notification is None:
            logger.info(
                "deliver_notification: notification %s not found; skipping", notification_id
            )
            return
        payload = {
            "id": notification.id,
            "type": notification.type,
            "payload_json": notification.payload_json,
            "created_at": notification.created_at.isoformat(),
        }
        push_notification(notification.user_id, payload)
        # TODO(P5-future): real push (FCM) + email delivery once provider creds land.
        logger.info(
            "deliver_notification: delivered notification %s to user %s (FCM/email TODO)",
            notification.id,
            notification.user_id,
        )
    except Exception:  # noqa: BLE001 — delivery is best-effort; never raise hard
        logger.warning(
            "deliver_notification failed for notification %s", notification_id, exc_info=True
        )
