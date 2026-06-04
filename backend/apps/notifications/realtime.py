"""Best-effort WS fan-out for the in-app notification stream.

Lives inside ``apps.notifications`` (NOT ``realtime/``) but mirrors
``realtime/broadcast.py``'s sync -> channel-layer pattern: a Celery task (sync) pushes
an event onto the async channel layer via ``async_to_sync``. It imports
``notifications_group`` from ``realtime.groups`` (read-only) so the group string never
drifts. **Best-effort**: if the channel layer is unavailable, the broadcast is
swallowed and logged — a delivery failure must never break the task or the request
that just committed the row.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from realtime.groups import notifications_group

logger = logging.getLogger(__name__)


def push_notification(user_id, payload: dict) -> None:
    """Push a notification onto the ``notifications.<user_id>`` group. Never raises."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            notifications_group(user_id),
            # ``type`` is dispatched by Channels to the consumer method of the same name
            # with dots -> underscores, so it MUST match NotificationsConsumer's handler
            # (``notification_event``), mirroring the trip.event/location.event contract.
            {"type": "notification.event", "data": payload},
        )
    except Exception:  # noqa: BLE001 — fan-out is best-effort; never break the caller
        logger.warning("push_notification failed for user %s", user_id, exc_info=True)
