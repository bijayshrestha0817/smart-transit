"""Best-effort WS fan-out for the admin SOS/alerts stream.

Lives inside ``apps.driver_logs`` (NOT ``realtime/``) but mirrors
``realtime/broadcast.py``'s sync -> channel-layer pattern: a sync REST service pushes
an event onto the async channel layer via ``async_to_sync``. It imports ``ALERTS``
from ``realtime.groups`` (read-only) so the group string never drifts. **Best-effort**:
if the channel layer is unavailable, the broadcast is swallowed and logged — a fan-out
failure must never break the SOS that just committed its DriverLog (the audit record).
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from realtime.groups import ALERTS

logger = logging.getLogger(__name__)


def push_alert(payload: dict) -> None:
    """Push an alert onto the ``alerts.admin`` group. Best-effort, never raises."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            ALERTS,
            # ``type`` is dispatched by Channels to the consumer method of the same name
            # with dots -> underscores, so it MUST match AlertsConsumer's handler
            # (``alert_event``), mirroring the trip.event/notification.event contract.
            {"type": "alert.event", "data": payload},
        )
    except Exception:  # noqa: BLE001 — fan-out is best-effort; never break the caller
        logger.warning("push_alert failed", exc_info=True)
