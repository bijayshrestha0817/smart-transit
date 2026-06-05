"""REST + RBAC tests for the notifications API: owner-scoped feed, read, read-all.

Auth uses ``client.force_authenticate(user=...)``. Body assertions read the rendered
``{data, meta, errors}`` envelope.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.notifications.enums import NotificationType
from apps.notifications.models import Notification

User = get_user_model()

PASSWORD = "StrongPass123!"
FEED_URL = "/api/v1/notifications/"
READ_ALL_URL = "/api/v1/notifications/read-all/"


def read_url(notification_id) -> str:
    return f"/api/v1/notifications/{notification_id}/read/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="rider@example.com", password=PASSWORD, is_verified=True)


@pytest.fixture
def other(db):
    return User.objects.create_user(email="other@example.com", password=PASSWORD, is_verified=True)


def _make(user, *, read=False, type=NotificationType.TRIP_COMPLETED) -> Notification:
    from django.utils import timezone

    return Notification.objects.create(
        user=user,
        type=type,
        payload_json={"trip_id": 1},
        read_at=timezone.now() if read else None,
    )


# ── Feed ─────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_feed_returns_only_own_notifications(client, user, other):
    mine = _make(user)
    _make(other)
    client.force_authenticate(user=user)
    resp = client.get(FEED_URL)
    assert resp.status_code == 200
    envelope = resp.json()
    assert "data" in envelope and "meta" in envelope and "errors" in envelope
    assert envelope["errors"] is None
    ids = {n["id"] for n in envelope["data"]}
    assert ids == {mine.id}


@pytest.mark.django_db
def test_feed_unread_filter(client, user):
    unread = _make(user)
    _make(user, read=True)
    client.force_authenticate(user=user)
    resp = client.get(FEED_URL, {"unread": "true"})
    assert resp.status_code == 200
    ids = {n["id"] for n in resp.json()["data"]}
    assert ids == {unread.id}


@pytest.mark.django_db
def test_feed_paginated_envelope(client, user):
    _make(user)
    client.force_authenticate(user=user)
    resp = client.get(FEED_URL)
    assert resp.status_code == 200
    assert resp.json()["meta"]["pagination"]["page_size"] == 20


@pytest.mark.django_db
def test_feed_requires_auth(client):
    assert client.get(FEED_URL).status_code == 401


# ── Mark one read ────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_mark_read_flips_state(client, user):
    notification = _make(user)
    client.force_authenticate(user=user)
    resp = client.post(read_url(notification.id), {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["data"]["read_at"] is not None
    notification.refresh_from_db()
    assert notification.read_at is not None


@pytest.mark.django_db
def test_mark_read_is_idempotent(client, user):
    notification = _make(user)
    client.force_authenticate(user=user)
    first = client.post(read_url(notification.id), {}, format="json")
    second = client.post(read_url(notification.id), {}, format="json")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["read_at"] == second.json()["data"]["read_at"]


@pytest.mark.django_db
def test_cannot_mark_another_users_notification(client, user, other):
    # IDOR check: foreign id -> 404 (owner-scoped queryset never leaks the row).
    foreign = _make(other)
    client.force_authenticate(user=user)
    resp = client.post(read_url(foreign.id), {}, format="json")
    assert resp.status_code == 404
    foreign.refresh_from_db()
    assert foreign.read_at is None  # untouched


@pytest.mark.django_db
def test_mark_missing_notification_returns_404(client, user):
    client.force_authenticate(user=user)
    assert client.post(read_url(999999), {}, format="json").status_code == 404


@pytest.mark.django_db
def test_mark_read_requires_auth(client, user):
    notification = _make(user)
    assert client.post(read_url(notification.id), {}, format="json").status_code == 401


# ── Mark all read ────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_read_all_flips_all_unread(client, user, other):
    _make(user)
    _make(user)
    untouched = _make(other)
    client.force_authenticate(user=user)
    resp = client.post(READ_ALL_URL, {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["data"]["updated"] == 2
    assert Notification.objects.filter(user=user, read_at__isnull=True).count() == 0
    untouched.refresh_from_db()
    assert untouched.read_at is None  # the other user's row is untouched


@pytest.mark.django_db
def test_read_all_requires_auth(client):
    assert client.post(READ_ALL_URL, {}, format="json").status_code == 401
