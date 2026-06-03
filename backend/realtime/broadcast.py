"""Sync → channel-layer bridge for non-WS producers (REST services, Celery tasks).

A DRF request runs in a sync worker but needs to push an event onto the async channel
layer (e.g. ``end_trip`` announcing ``TRIP_COMPLETED`` to the trip group). ``async_to_sync``
crosses that boundary. This is **best-effort**: if the channel layer is unavailable, the
broadcast is swallowed and logged — a fan-out failure must never break the REST request
that just committed real state.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import trip_group

logger = logging.getLogger(__name__)


def broadcast_trip_event(trip_id, event_type: str, data: dict | None = None) -> None:
    """Push a lifecycle event onto the ``trip.<id>`` group. Best-effort, never raises."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            trip_group(trip_id),
            {"type": "trip.event", "data": {"event": event_type, **(data or {})}},
        )
    except Exception:  # noqa: BLE001 — fan-out is best-effort; never break the caller
        logger.warning("broadcast_trip_event failed for trip %s", trip_id, exc_info=True)
