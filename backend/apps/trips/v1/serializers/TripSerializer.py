"""Trip serializers — read, admin write, action payloads, and the active/fleet shape."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.buses.repository import BusRepository, DriverRepository, RouteRepository
from apps.trips.enums import TripStatus
from apps.trips.models import Trip

User = get_user_model()


class TripSerializer(serializers.ModelSerializer):
    """Read representation of a trip."""

    bus_plate = serializers.CharField(source="bus.plate", read_only=True)
    route_name = serializers.CharField(source="route.name", read_only=True)
    route_color = serializers.CharField(source="route.color", read_only=True)
    driver_email = serializers.CharField(source="driver.email", read_only=True)

    class Meta:
        model = Trip
        fields = (
            "id",
            "bus",
            "bus_plate",
            "route",
            "route_name",
            "route_color",
            "driver",
            "driver_email",
            "status",
            "start_time",
            "end_time",
            "passenger_count",
            "created_at",
        )
        read_only_fields = fields


class AdminTripWriteSerializer(serializers.ModelSerializer):
    """Admin scheduling payload — validates bus/route/driver against the repositories."""

    status = serializers.ChoiceField(
        choices=TripStatus.choices, required=False, default=TripStatus.SCHEDULED
    )
    # Declared over the full User queryset so the model's ``limit_choices_to`` doesn't
    # inject a ``does_not_exist`` for a non-driver — validate_driver owns the role check
    # and emits the stable ``invalid_driver`` code.
    driver = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Trip
        fields = ("bus", "route", "driver", "status")

    def validate_bus(self, value):
        if BusRepository.get_by_id(value.id) is None:
            raise serializers.ValidationError("No active bus with this id.", code="invalid_bus")
        return value

    def validate_route(self, value):
        if RouteRepository.get_by_id(value.id) is None:
            raise serializers.ValidationError("No active route with this id.", code="invalid_route")
        return value

    def validate_driver(self, value):
        if not DriverRepository.driver_exists(value.id):
            raise serializers.ValidationError(
                "No active driver with this id.", code="invalid_driver"
            )
        return value


class PassengerCountSerializer(serializers.Serializer):
    """Driver-reported passenger count for a trip."""

    count = serializers.IntegerField(min_value=0)


class GpsPointSerializer(serializers.Serializer):
    """One GPS breadcrumb in an offline-flush batch (carries a client timestamp)."""

    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    speed = serializers.DecimalField(max_digits=5, decimal_places=2)
    heading = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    timestamp = serializers.DateTimeField()


class GpsBatchSerializer(serializers.Serializer):
    """A batch of buffered GPS points uploaded on reconnect."""

    # Cap the batch (anti-DoS); an empty list is accepted as a no-op.
    points = GpsPointSerializer(many=True, max_length=1000)


class LiveGpsPointSerializer(serializers.Serializer):
    """One live GPS point streamed in over the WebSocket.

    Same field rules as ``GpsPointSerializer`` but WITHOUT ``timestamp``: live points
    are server-stamped authoritatively (only the offline-flush/REST batch path carries
    client timestamps). Validating here keeps a bad point (missing ``speed``, non-numeric
    or out-of-range coordinate) from reaching the buffer and blowing up the whole batch
    on flush.
    """

    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    speed = serializers.DecimalField(max_digits=5, decimal_places=2)
    heading = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )


class LastPositionSerializer(serializers.Serializer):
    """The latest GPS breadcrumb for a trip, or null when none recorded yet."""

    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    speed = serializers.DecimalField(max_digits=5, decimal_places=2)
    heading = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    timestamp = serializers.DateTimeField()


class EtaSerializer(serializers.Serializer):
    """Baseline heuristic ETA to the next stop (see ``EtaService``)."""

    minutes = serializers.IntegerField(allow_null=True)
    seconds = serializers.IntegerField(allow_null=True)
    next_stop = serializers.CharField(allow_null=True)
    # gps | schedule | unavailable — how the estimate was derived (drives UI confidence).
    source = serializers.ChoiceField(choices=["gps", "schedule", "unavailable"])


class ActiveTripSerializer(serializers.Serializer):
    """Trip + its last known position + baseline ETA (passenger ``/trips/active/`` and
    admin ``/admin/fleet/``)."""

    trip = TripSerializer()
    last_position = LastPositionSerializer(allow_null=True)
    eta = EtaSerializer(allow_null=True)
