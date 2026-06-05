"""WS fan-out contract test for the notification stream.

Locks the producer/consumer wire contract: ``push_notification`` MUST emit a message
whose ``type`` dispatches to ``NotificationsConsumer.notification_event`` (i.e.
``"notification.event"``), so a connected client actually receives the payload. With
the wrong type (``"notification.message"``) Channels has no matching handler, raises
"No handler for message type notification.message", and the client receives nothing —
which the pre-fix tests never caught (they only asserted the broadcast was attempted).

Async + DB-touching, so it mirrors ``realtime/tests/test_consumers.py``: the real ASGI
app over the in-memory channel layer, under ``@pytest.mark.django_db(transaction=True)``.
"""

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from apps.notifications.realtime import push_notification
from config.asgi import application

User = get_user_model()

PASSWORD = "StrongPass123!"


def _make_user(email="rider@example.com"):
    return User.objects.create_user(email=email, password=PASSWORD)


def _token_for(user) -> str:
    return str(AccessToken.for_user(user))


def _connect(path, token):
    headers = [(b"origin", b"http://localhost"), (b"host", b"localhost")]
    headers.append((b"cookie", f"st_access={token}".encode()))
    return WebsocketCommunicator(application, path, headers=headers)


@pytest.mark.django_db(transaction=True)
async def test_push_notification_reaches_connected_consumer():
    """A connected NotificationsConsumer receives the payload pushed by the producer.

    Fails without FIX (type ``notification.message`` -> no handler -> nothing arrives);
    passes once the producer emits ``notification.event`` to match the handler.
    """
    user = await database_sync_to_async(_make_user)()
    token = await database_sync_to_async(_token_for)(user)

    comm = _connect("/ws/notifications/", token)
    assert (await comm.connect())[0] is True

    payload = {"id": 1, "type": "TRIP_COMPLETED", "payload_json": {"trip_id": 7}}
    # push_notification is sync (mirrors a Celery worker); cross the boundary explicitly.
    await database_sync_to_async(push_notification)(user.id, payload)

    received = await comm.receive_json_from()
    assert received == payload

    await comm.disconnect()
