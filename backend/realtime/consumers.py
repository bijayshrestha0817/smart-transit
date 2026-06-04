from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.trips.repository import TripRepository
from apps.trips.v1.serializers import LiveGpsPointSerializer
from apps.trips.v1.service import TripService

from .groups import ALERTS, FLEET, notifications_group, trip_group

# Flush buffered GPS points to the DB once this many have accumulated. Disconnect
# flushes any remainder, so no points are lost between flush boundaries.
GPS_FLUSH_SIZE = 10

# WebSocket close codes — private-use 4000–4999 range (api-contract §8). NOT HTTP codes:
# 4401/4403 echo HTTP 401/403, but the leading "4" keeps them valid WS close codes.
CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403


def _is_authenticated(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


class DriverTripConsumer(AsyncJsonWebsocketConsumer):
    """``/ws/driver/{trip_id}/`` — the trip's driver streams GPS in.

    Inbound points are fanned out to passengers/fleet immediately, then buffered and
    persisted in batches. Only the driver assigned to the trip may connect.
    """

    async def connect(self):
        self.user = self.scope["user"]
        if not _is_authenticated(self.user):
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return

        self.trip_id = self.scope["url_route"]["kwargs"]["trip_id"]
        self.trip = await database_sync_to_async(TripRepository.get_by_id)(self.trip_id)

        # Missing trip, wrong role, or not this driver's trip -> forbidden (don't leak existence).
        if (
            self.trip is None
            or self.user.role != UserRole.DRIVER
            or self.trip.driver_id != self.user.id
        ):
            await self.close(code=CLOSE_FORBIDDEN)
            return

        self._buffer: list[dict] = []
        self.group = trip_group(self.trip_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def receive_json(self, content, **kwargs):
        """Treat each message as a live GPS point: {lat, lng, speed, heading?}."""
        # VALIDATE the inbound point up front (same field rules as the REST batch, minus
        # the client timestamp). A bad point (missing speed, non-numeric/out-of-range
        # coordinate) is rejected here so it never reaches the buffer and rolls back an
        # otherwise-good batch on flush.
        serializer = LiveGpsPointSerializer(data=content)
        if not serializer.is_valid():
            await self.send_json({"error": "invalid_gps_point", "detail": serializer.errors})
            return
        validated = serializer.validated_data

        # SERVER timestamp for live points (the REST batch path carries CLIENT timestamps
        # for offline replay; live WS points are stamped here, authoritatively).
        ts = timezone.now()
        point = {
            "lat": validated["lat"],
            "lng": validated["lng"],
            "speed": validated["speed"],
            "heading": validated.get("heading"),
            "timestamp": ts,
        }

        # FAN OUT FIRST (architecture §4: broadcast does not wait on the DB write).
        # Decimals are str()'d so the payload is JSON-serialisable; DRF normalises them
        # to the declared decimal_places, so the wire value matches what the client sent.
        heading = point["heading"]
        event = {
            "type": "location.event",
            "data": {
                "lat": str(point["lat"]),
                "lng": str(point["lng"]),
                "speed": str(point["speed"]),
                "heading": None if heading is None else str(heading),
                "trip_id": self.trip_id,
                "ts": ts.isoformat(),
            },
        }
        await self.channel_layer.group_send(self.group, event)
        await self.channel_layer.group_send(FLEET, event)

        # THEN buffer + flush in batches.
        self._buffer.append(point)
        if len(self._buffer) >= GPS_FLUSH_SIZE:
            await self._flush()

    async def disconnect(self, code):
        # Persist anything left in the buffer before leaving so no points are lost.
        if getattr(self, "_buffer", None):
            await self._flush()
        if getattr(self, "group", None):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def _flush(self):
        if not self._buffer:
            return
        batch = self._buffer
        self._buffer = []
        # ingest_gps re-asserts that self.user is the trip's driver. self.user IS the
        # driver (enforced in connect), so it passes — this is the deliberate slice-2
        # ownership guard protecting the non-DRF WS write path.
        await database_sync_to_async(TripService.ingest_gps)(self.trip, self.user, batch)

    async def location_event(self, event):
        await self.send_json(event["data"])

    async def trip_event(self, event):
        # The driver shares the trip.<id> group, so it also receives lifecycle events
        # (e.g. TRIP_COMPLETED from end_trip). Without this handler Channels raises
        # "No handler for message type trip.event" and kills the socket task, bypassing
        # disconnect()/_flush() and losing buffered points.
        await self.send_json(event["data"])


class TripConsumer(AsyncJsonWebsocketConsumer):
    """``/ws/trip/{trip_id}/`` — passengers watch a bus. Read-only fan-out target."""

    async def connect(self):
        user = self.scope["user"]
        if not _is_authenticated(user):
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        self.trip_id = self.scope["url_route"]["kwargs"]["trip_id"]
        self.group = trip_group(self.trip_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if getattr(self, "group", None):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def location_event(self, event):
        await self.send_json(event["data"])

    async def trip_event(self, event):
        # Lifecycle events, e.g. {"event": "TRIP_COMPLETED"}.
        await self.send_json(event["data"])


class FleetConsumer(AsyncJsonWebsocketConsumer):
    """``/ws/fleet/`` — admin overview of every active bus position."""

    async def connect(self):
        user = self.scope["user"]
        if not _is_authenticated(user):
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        if user.role != UserRole.ADMIN:
            await self.close(code=CLOSE_FORBIDDEN)
            return
        await self.channel_layer.group_add(FLEET, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(FLEET, self.channel_name)

    async def location_event(self, event):
        await self.send_json(event["data"])


class AlertsConsumer(AsyncJsonWebsocketConsumer):
    """``/ws/alerts/`` — admin anomaly/SOS/deviation stream. Producer arrives in P5;
    this channel only establishes the subscription for now."""

    async def connect(self):
        user = self.scope["user"]
        if not _is_authenticated(user):
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        if user.role != UserRole.ADMIN:
            await self.close(code=CLOSE_FORBIDDEN)
            return
        await self.channel_layer.group_add(ALERTS, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(ALERTS, self.channel_name)

    async def alert_event(self, event):
        await self.send_json(event["data"])


class NotificationsConsumer(AsyncJsonWebsocketConsumer):
    """``/ws/notifications/`` — per-user in-app notification stream (any authed user).
    Producer arrives later; this channel only establishes the subscription for now."""

    async def connect(self):
        user = self.scope["user"]
        if not _is_authenticated(user):
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        self.group = notifications_group(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if getattr(self, "group", None):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def notification_event(self, event):
        await self.send_json(event["data"])
