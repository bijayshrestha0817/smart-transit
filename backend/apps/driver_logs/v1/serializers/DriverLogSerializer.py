"""Driver log serializers — read representation + the two write payloads.

Ownership of a supplied ``trip`` is enforced in the service (it raises
``invalid_trip``), so the write serializers only validate shape: ``event_type`` against
the enum and ``trip`` as an optional integer id.
"""

from rest_framework import serializers

from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.models import DriverLog


class DriverLogSerializer(serializers.ModelSerializer):
    """Read representation of a driver log."""

    class Meta:
        model = DriverLog
        fields = (
            "id",
            "event_type",
            "notes",
            "trip",
            "timestamp",
            "created_at",
        )
        read_only_fields = fields


class CreateDriverLogSerializer(serializers.Serializer):
    """`POST /driver/logs/` payload — any event type (including sos), optional trip."""

    event_type = serializers.ChoiceField(choices=DriverLogEventType.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # Validate shape only; the service resolves the id and enforces driver ownership
    # (emitting the stable ``invalid_trip`` code) so absence vs. unowned never leaks.
    trip = serializers.IntegerField(required=False, allow_null=True)


class SosSerializer(serializers.Serializer):
    """`POST /driver/sos/` payload — notes + trip are both optional; event type is sos."""

    notes = serializers.CharField(required=False, allow_blank=True, default="")
    trip = serializers.IntegerField(required=False, allow_null=True)
