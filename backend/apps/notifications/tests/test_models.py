"""Model-layer tests: defaults, the unread index, and soft delete."""

import pytest
from django.contrib.auth import get_user_model

from apps.notifications.enums import NotificationType
from apps.notifications.models import Notification

User = get_user_model()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(email="rider@example.com", password="Demo1234!")


@pytest.mark.django_db
def test_create_defaults_to_unread(user):
    notification = Notification.objects.create(user=user, type=NotificationType.TRIP_COMPLETED)
    assert notification.read_at is None  # null read_at == unread
    assert notification.payload_json == {}
    assert notification.is_deleted is False


@pytest.mark.django_db
def test_payload_json_persists(user):
    notification = Notification.objects.create(
        user=user,
        type=NotificationType.TRIP_COMPLETED,
        payload_json={"trip_id": 7, "route_name": "Ring Road"},
    )
    notification.refresh_from_db()
    assert notification.payload_json == {"trip_id": 7, "route_name": "Ring Road"}


@pytest.mark.django_db
def test_user_read_at_index_present():
    index_fields = [tuple(idx.fields) for idx in Notification._meta.indexes]
    assert ("user", "read_at") in index_fields


@pytest.mark.django_db
def test_soft_delete_hides_row(user):
    notification = Notification.objects.create(user=user, type=NotificationType.TRIP_COMPLETED)
    notification.delete()
    assert not Notification.objects.filter(id=notification.id).exists()
    assert Notification.all_objects.get(id=notification.id).is_deleted is True
