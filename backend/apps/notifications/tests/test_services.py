"""Service-layer tests: create + eager delivery, feed filtering, mark_read/all_read."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.enums import NotificationType
from apps.notifications.models import Notification
from apps.notifications.v1.service import NotificationService

User = get_user_model()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(email="rider@example.com", password="Demo1234!")


@pytest.fixture
def other(db) -> User:
    return User.objects.create_user(email="other@example.com", password="Demo1234!")


@pytest.mark.django_db
def test_create_persists_row(user):
    notification = NotificationService.create(user, NotificationType.TRIP_COMPLETED, {"trip_id": 1})
    assert notification.id is not None
    assert notification.user_id == user.id
    assert notification.read_at is None
    assert Notification.objects.filter(id=notification.id).exists()


@pytest.mark.django_db
def test_create_delivers_inline_under_eager(user):
    # create() defers delivery to transaction.on_commit. pytest-django wraps each test
    # in an outer transaction that never commits, so capture the on_commit callbacks and
    # run them explicitly — under CELERY_TASK_ALWAYS_EAGER the enqueued task runs inline.
    with patch("apps.notifications.tasks.push_notification") as push:
        with TestCase.captureOnCommitCallbacks(execute=True):
            notification = NotificationService.create(user, NotificationType.TRIP_COMPLETED, {})
    assert push.called  # delivery was attempted inline, without raising
    args, _ = push.call_args
    assert args[0] == user.id
    assert args[1]["id"] == notification.id


@pytest.mark.django_db
def test_create_swallows_enqueue_failure_on_commit(user):
    # Simulate a broker outage: .delay() raises at enqueue time (e.g. Redis down ->
    # kombu OperationalError). This raise happens inside the on_commit callback, AFTER
    # the row commits and OUTSIDE the signal/service try-contexts, so an unguarded
    # enqueue would propagate into the request. _enqueue_delivery must swallow it.
    with patch("apps.notifications.v1.service.NotificationService.deliver_notification") as task:
        task.delay.side_effect = RuntimeError("broker unreachable")
        with TestCase.captureOnCommitCallbacks(execute=True):
            notification = NotificationService.create(user, NotificationType.TRIP_COMPLETED, {})
    # The committed write survives and the failed enqueue did not raise into the caller.
    assert task.delay.called
    assert Notification.objects.filter(id=notification.id).exists()


@pytest.mark.django_db
def test_feed_unread_filter_and_ordering(user):
    first = NotificationService.create(user, NotificationType.TRIP_COMPLETED, {})
    second = NotificationService.create(user, NotificationType.ROUTE_DELAY, {})
    NotificationService.mark_read(first)

    all_feed = list(NotificationService.feed(user))
    # Newest first.
    assert all_feed[0].id == second.id
    assert {n.id for n in all_feed} == {first.id, second.id}

    unread = list(NotificationService.feed(user, unread_only=True))
    assert [n.id for n in unread] == [second.id]


@pytest.mark.django_db
def test_feed_is_owner_scoped(user, other):
    mine = NotificationService.create(user, NotificationType.TRIP_COMPLETED, {})
    NotificationService.create(other, NotificationType.TRIP_COMPLETED, {})
    feed_ids = {n.id for n in NotificationService.feed(user)}
    assert feed_ids == {mine.id}


@pytest.mark.django_db
def test_mark_read_is_idempotent(user):
    notification = NotificationService.create(user, NotificationType.TRIP_COMPLETED, {})
    NotificationService.mark_read(notification)
    first_read_at = notification.read_at
    assert first_read_at is not None
    # Second call is a no-op — read_at unchanged.
    NotificationService.mark_read(notification)
    assert notification.read_at == first_read_at


@pytest.mark.django_db
def test_mark_all_read_returns_count_and_zeroes_unread(user):
    NotificationService.create(user, NotificationType.TRIP_COMPLETED, {})
    NotificationService.create(user, NotificationType.ROUTE_DELAY, {})
    count = NotificationService.mark_all_read(user)
    assert count == 2
    assert NotificationService.feed(user, unread_only=True).count() == 0
    # A second sweep touches nothing.
    assert NotificationService.mark_all_read(user) == 0


@pytest.mark.django_db
def test_mark_all_read_only_touches_own(user, other):
    NotificationService.create(user, NotificationType.TRIP_COMPLETED, {})
    other_n = NotificationService.create(other, NotificationType.TRIP_COMPLETED, {})
    NotificationService.mark_all_read(user)
    other_n.refresh_from_db()
    assert other_n.read_at is None  # the other user's unread row is untouched
