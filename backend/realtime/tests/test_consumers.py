"""WebSocket consumer tests (auth, RBAC, fan-out, buffered persist, lifecycle events).

These are async and touch the DB, so they run on the in-memory channel layer
(``config.settings.test``) and under ``@pytest.mark.django_db(transaction=True)`` — the
consumers persist via ``database_sync_to_async`` on a separate thread, which needs a
committed (non-savepoint-wrapped) transaction to see the rows the test creates. DB work
is therefore wrapped in ``database_sync_to_async`` so both the test coroutine and the
consumer thread share the same SQLite connection state.
"""

import pytest
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from apps.buses.models import Bus, Route
from apps.trips.enums import TripStatus
from apps.trips.models import GpsLocation, Trip
from apps.trips.v1.service import TripService
from config.asgi import application
from realtime.consumers import GPS_FLUSH_SIZE

User = get_user_model()

PASSWORD = "StrongPass123!"


# ── Sync helpers (called via database_sync_to_async from async tests) ─────────
def _make_driver(email="driver@example.com"):
    return User.objects.create_user(email=email, password=PASSWORD, role=User.Roles.DRIVER)


def _make_passenger(email="rider@example.com"):
    return User.objects.create_user(email=email, password=PASSWORD)


def _make_admin(email="admin@example.com"):
    return User.objects.create_user(email=email, password=PASSWORD, role=User.Roles.ADMIN)


def _make_trip(driver, status=TripStatus.IN_PROGRESS):
    route = Route.objects.create(name="Ring Road", color="#1E88E5", estimated_duration=55)
    bus = Bus.objects.create(plate=f"BA 1 KHA {driver.id:04d}", capacity=40)
    return Trip.objects.create(bus=bus, route=route, driver=driver, status=status)


def _token_for(user) -> str:
    return str(AccessToken.for_user(user))


def _connect(path, token=None):
    """Build a communicator against the real ASGI app, optionally with a cookie token.

    Sends an ``Origin``/``Host`` matching ``ALLOWED_HOSTS`` so the production
    ``AllowedHostsOriginValidator`` accepts the handshake (it denies an absent/foreign
    origin), exercising the real ASGI stack rather than bypassing it.
    """
    headers = [(b"origin", b"http://localhost"), (b"host", b"localhost")]
    if token is not None:
        headers.append((b"cookie", f"st_access={token}".encode()))
    return WebsocketCommunicator(application, path, headers=headers)


def _gps_count(trip):
    return GpsLocation.objects.filter(trip=trip).count()


# ── AUTH ──────────────────────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_driver_connect_without_token_is_rejected():
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)

    comm = _connect(f"/ws/driver/{trip.id}/")  # no token
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4401


@pytest.mark.django_db(transaction=True)
async def test_driver_connect_with_valid_own_token_is_accepted():
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    token = await database_sync_to_async(_token_for)(driver)

    comm = _connect(f"/ws/driver/{trip.id}/", token)
    connected, _ = await comm.connect()
    assert connected is True
    await comm.disconnect()


# ── FORBIDDEN (4403) ───────────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_passenger_token_on_driver_channel_is_forbidden():
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    passenger = await database_sync_to_async(_make_passenger)()
    token = await database_sync_to_async(_token_for)(passenger)

    comm = _connect(f"/ws/driver/{trip.id}/", token)
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4403


@pytest.mark.django_db(transaction=True)
async def test_driver_on_another_drivers_trip_is_forbidden():
    owner = await database_sync_to_async(_make_driver)("owner@example.com")
    trip = await database_sync_to_async(_make_trip)(owner)
    intruder = await database_sync_to_async(_make_driver)("intruder@example.com")
    token = await database_sync_to_async(_token_for)(intruder)

    comm = _connect(f"/ws/driver/{trip.id}/", token)
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4403


@pytest.mark.django_db(transaction=True)
async def test_non_admin_on_fleet_channel_is_forbidden():
    passenger = await database_sync_to_async(_make_passenger)()
    token = await database_sync_to_async(_token_for)(passenger)

    comm = _connect("/ws/fleet/", token)
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4403


@pytest.mark.django_db(transaction=True)
async def test_admin_on_fleet_channel_is_accepted():
    admin = await database_sync_to_async(_make_admin)()
    token = await database_sync_to_async(_token_for)(admin)

    comm = _connect("/ws/fleet/", token)
    connected, _ = await comm.connect()
    assert connected is True
    await comm.disconnect()


# ── FAN-OUT (driver -> passenger) ───────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_driver_gps_fans_out_to_passenger():
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    passenger = await database_sync_to_async(_make_passenger)()
    driver_token = await database_sync_to_async(_token_for)(driver)
    pax_token = await database_sync_to_async(_token_for)(passenger)

    driver_comm = _connect(f"/ws/driver/{trip.id}/", driver_token)
    assert (await driver_comm.connect())[0] is True
    pax_comm = _connect(f"/ws/trip/{trip.id}/", pax_token)
    assert (await pax_comm.connect())[0] is True

    await driver_comm.send_json_to(
        {"lat": "27.700000", "lng": "85.300000", "speed": "12.50", "heading": "90.00"}
    )

    received = await pax_comm.receive_json_from()
    assert received["lat"] == "27.700000"
    assert received["lng"] == "85.300000"
    assert received["speed"] == "12.50"
    assert received["heading"] == "90.00"
    assert received["trip_id"] == str(trip.id)
    assert "ts" in received

    await driver_comm.disconnect()
    await pax_comm.disconnect()


# ── BUFFERED WRITE ──────────────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_buffered_write_flushes_at_threshold_and_on_disconnect():
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    token = await database_sync_to_async(_token_for)(driver)

    comm = _connect(f"/ws/driver/{trip.id}/", token)
    assert (await comm.connect())[0] is True

    point = {"lat": "27.700000", "lng": "85.300000", "speed": "10.00", "heading": "45.00"}

    # Exactly one flush worth -> persisted once the threshold is hit.
    for _ in range(GPS_FLUSH_SIZE):
        await comm.send_json_to(point)
        await comm.receive_json_from()  # drain the fan-out echo back to ourselves
    assert await database_sync_to_async(_gps_count)(trip) == GPS_FLUSH_SIZE

    # A few more below the threshold sit in the buffer...
    remainder = 3
    for _ in range(remainder):
        await comm.send_json_to(point)
        await comm.receive_json_from()
    # ...and are flushed on disconnect (no lost points).
    await comm.disconnect()
    assert await database_sync_to_async(_gps_count)(trip) == GPS_FLUSH_SIZE + remainder


# ── TRIP_COMPLETED lifecycle event ──────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_passenger_receives_trip_completed_event():
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    passenger = await database_sync_to_async(_make_passenger)()
    pax_token = await database_sync_to_async(_token_for)(passenger)

    pax_comm = _connect(f"/ws/trip/{trip.id}/", pax_token)
    assert (await pax_comm.connect())[0] is True

    # end_trip broadcasts TRIP_COMPLETED on the trip group after committing.
    await database_sync_to_async(TripService.end_trip)(trip, driver)

    event = await pax_comm.receive_json_from()
    assert event["event"] == "TRIP_COMPLETED"

    # The trip really did complete.
    refreshed = await sync_to_async(Trip.objects.get)(id=trip.id)
    assert refreshed.status == TripStatus.COMPLETED

    await pax_comm.disconnect()


# ── REGRESSION: driver socket survives its own trip ending ───────────────────────
@pytest.mark.django_db(transaction=True)
async def test_driver_socket_survives_own_trip_completed_and_keeps_buffered_points():
    """The driver shares the trip.<id> group, so end_trip's TRIP_COMPLETED reaches it.

    Without a ``trip_event`` handler Channels raises "No handler for message type
    trip.event" and kills the consumer task — bypassing disconnect()/_flush() and
    dropping the buffered points. This must FAIL without FIX 1 and pass with it.
    """
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    token = await database_sync_to_async(_token_for)(driver)

    comm = _connect(f"/ws/driver/{trip.id}/", token)
    assert (await comm.connect())[0] is True

    point = {"lat": "27.700000", "lng": "85.300000", "speed": "10.00", "heading": "45.00"}
    sent = 3  # sub-threshold: stays buffered, not yet flushed
    assert sent < GPS_FLUSH_SIZE
    for _ in range(sent):
        await comm.send_json_to(point)
        await comm.receive_json_from()  # drain our own location echo

    # end_trip broadcasts TRIP_COMPLETED to the trip group while the driver is connected.
    await database_sync_to_async(TripService.end_trip)(trip, driver)

    # The driver socket stays alive and receives the lifecycle event.
    event = await comm.receive_json_from()
    assert event["event"] == "TRIP_COMPLETED"

    # Buffered points survive — disconnect's _flush() still runs and persists them.
    await comm.disconnect()
    assert await database_sync_to_async(_gps_count)(trip) == sent


# ── LATENCY INVARIANT: fan-out precedes the DB write ─────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_fan_out_happens_before_db_write(monkeypatch):
    """Architecture §4: broadcast does not wait on the DB. The passenger sees the point
    while the persisted row count is still 0 — proving fan-out ran before persist."""
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    passenger = await database_sync_to_async(_make_passenger)()
    driver_token = await database_sync_to_async(_token_for)(driver)
    pax_token = await database_sync_to_async(_token_for)(passenger)

    seen_at_flush = {}
    original_ingest = TripService.ingest_gps

    def _recording_ingest(_trip, by_user, points):
        # Capture how many rows existed at the moment the flush began writing.
        seen_at_flush["count"] = GpsLocation.objects.filter(trip=_trip).count()
        return original_ingest(_trip, by_user, points)

    monkeypatch.setattr(TripService, "ingest_gps", staticmethod(_recording_ingest))

    driver_comm = _connect(f"/ws/driver/{trip.id}/", driver_token)
    assert (await driver_comm.connect())[0] is True
    pax_comm = _connect(f"/ws/trip/{trip.id}/", pax_token)
    assert (await pax_comm.connect())[0] is True

    await driver_comm.send_json_to(
        {"lat": "27.700000", "lng": "85.300000", "speed": "12.50", "heading": "90.00"}
    )

    # The passenger receives the fan-out event before any DB write happens (single
    # sub-threshold point -> still buffered, not yet persisted).
    received = await pax_comm.receive_json_from()
    assert received["trip_id"] == str(trip.id)
    assert await database_sync_to_async(_gps_count)(trip) == 0

    # Disconnect flushes the buffer; the recorded pre-insert count proves the row did
    # not exist when fan-out happened.
    await driver_comm.disconnect()
    assert seen_at_flush["count"] == 0
    assert await database_sync_to_async(_gps_count)(trip) == 1

    await pax_comm.disconnect()


# ── FLEET fan-out (driver -> admin) ──────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_driver_gps_fans_out_to_fleet_admin():
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    admin = await database_sync_to_async(_make_admin)()
    driver_token = await database_sync_to_async(_token_for)(driver)
    admin_token = await database_sync_to_async(_token_for)(admin)

    driver_comm = _connect(f"/ws/driver/{trip.id}/", driver_token)
    assert (await driver_comm.connect())[0] is True
    fleet_comm = _connect("/ws/fleet/", admin_token)
    assert (await fleet_comm.connect())[0] is True

    await driver_comm.send_json_to(
        {"lat": "27.700000", "lng": "85.300000", "speed": "12.50", "heading": "90.00"}
    )

    received = await fleet_comm.receive_json_from()
    assert received["lat"] == "27.700000"
    assert received["lng"] == "85.300000"
    assert received["trip_id"] == str(trip.id)

    await driver_comm.disconnect()
    await fleet_comm.disconnect()


# ── INBOUND VALIDATION ───────────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_invalid_gps_point_is_rejected_and_not_buffered():
    """A point missing the NOT NULL ``speed`` is rejected up front, never reaching the
    buffer (so it can't roll back an otherwise-good batch on flush)."""
    driver = await database_sync_to_async(_make_driver)()
    trip = await database_sync_to_async(_make_trip)(driver)
    token = await database_sync_to_async(_token_for)(driver)

    comm = _connect(f"/ws/driver/{trip.id}/", token)
    assert (await comm.connect())[0] is True

    # Missing speed -> rejected with an error frame, no fan-out, no buffering.
    await comm.send_json_to({"lat": "27.700000", "lng": "85.300000"})
    error = await comm.receive_json_from()
    assert error["error"] == "invalid_gps_point"
    assert "speed" in error["detail"]

    await comm.disconnect()
    assert await database_sync_to_async(_gps_count)(trip) == 0


# ── ALERTS auth gates ────────────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_alerts_channel_rejects_anonymous():
    comm = _connect("/ws/alerts/")  # no token
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4401


@pytest.mark.django_db(transaction=True)
async def test_alerts_channel_rejects_non_admin():
    passenger = await database_sync_to_async(_make_passenger)()
    token = await database_sync_to_async(_token_for)(passenger)

    comm = _connect("/ws/alerts/", token)
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4403


@pytest.mark.django_db(transaction=True)
async def test_alerts_channel_accepts_admin():
    admin = await database_sync_to_async(_make_admin)()
    token = await database_sync_to_async(_token_for)(admin)

    comm = _connect("/ws/alerts/", token)
    connected, _ = await comm.connect()
    assert connected is True
    await comm.disconnect()


# ── NOTIFICATIONS auth gates ─────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
async def test_notifications_channel_rejects_anonymous():
    comm = _connect("/ws/notifications/")  # no token
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4401


@pytest.mark.django_db(transaction=True)
async def test_notifications_channel_accepts_authed_user():
    passenger = await database_sync_to_async(_make_passenger)()
    token = await database_sync_to_async(_token_for)(passenger)

    comm = _connect("/ws/notifications/", token)
    connected, _ = await comm.connect()
    assert connected is True
    await comm.disconnect()
