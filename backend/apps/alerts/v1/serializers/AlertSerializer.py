"""Alert serializer — read shape for the REST feed AND the WS broadcast payload.

The same shape is what ``AlertService`` serializes onto the ``alerts.admin`` group, so the
frontend's REST seed and live frames are identical (one client-side type).
"""

from rest_framework import serializers

from apps.alerts.models import Alert


class AlertSerializer(serializers.ModelSerializer):
    """Read representation of an alert (incident-log row + live frame)."""

    trip_route = serializers.CharField(source="trip.route.name", read_only=True, default=None)
    driver_email = serializers.CharField(source="driver.email", read_only=True, default=None)

    class Meta:
        model = Alert
        fields = (
            "id",
            "type",
            "severity",
            "message",
            "trip",
            "trip_route",
            "driver",
            "driver_email",
            "status",
            "payload_json",
            "acknowledged_at",
            "created_at",
        )
        read_only_fields = fields
