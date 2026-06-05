"""Notification serializer — read-only feed representation."""

from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Read representation of a notification (all fields read-only)."""

    class Meta:
        model = Notification
        fields = (
            "id",
            "type",
            "payload_json",
            "read_at",
            "created_at",
        )
        read_only_fields = fields


class ReadAllResponseSerializer(serializers.Serializer):
    """Response shape for ``POST /notifications/read-all/`` — count of rows marked read."""

    updated = serializers.IntegerField()
