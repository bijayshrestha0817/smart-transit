"""Serializers for routes, stops, buses, and driver management.

Validation lives here; views stay thin. The ``{data, meta, errors}`` envelope is
applied by the renderer/exception handler, so these never assemble it by hand —
they raise ``serializers.ValidationError`` with stable machine ``code=`` strings.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Bus, BusStop, Route

User = get_user_model()


# ── Bus stops ────────────────────────────────────────────────────────────────
class BusStopSerializer(serializers.ModelSerializer):
    """Read representation of a stop."""

    class Meta:
        model = BusStop
        fields = ("id", "name", "lat", "lng", "route", "sequence", "created_at")
        read_only_fields = fields


class BusStopWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusStop
        fields = ("name", "lat", "lng", "route", "sequence")


# ── Routes ───────────────────────────────────────────────────────────────────
class RouteListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("id", "name", "color", "estimated_duration", "created_at")
        read_only_fields = fields


class RouteDetailSerializer(serializers.ModelSerializer):
    stops = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = (
            "id",
            "name",
            "color",
            "estimated_duration",
            "polyline_json",
            "created_at",
            "stops",
        )
        read_only_fields = fields

    def get_stops(self, obj: Route) -> list[dict]:
        # Explicit ordering so the map draws stops in route order regardless of
        # any prefetch/annotation reordering.
        stops = obj.stops.all().order_by("sequence")
        return BusStopSerializer(stops, many=True).data


class RouteWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("name", "color", "estimated_duration", "polyline_json")


# ── Buses ────────────────────────────────────────────────────────────────────
class BusSerializer(serializers.ModelSerializer):
    assigned_driver_email = serializers.CharField(
        source="assigned_driver.email", read_only=True, default=None
    )

    class Meta:
        model = Bus
        fields = (
            "id",
            "plate",
            "capacity",
            "status",
            "assigned_driver",
            "assigned_driver_email",
            "created_at",
        )
        read_only_fields = fields


class BusWriteSerializer(serializers.ModelSerializer):
    # Declared explicitly (no validators) so the model's partial UniqueConstraint
    # doesn't inject an auto ``UniqueValidator`` — ``validate_plate`` owns the check
    # and emits the stable ``duplicate_plate`` code.
    plate = serializers.CharField(max_length=20)

    class Meta:
        model = Bus
        fields = ("plate", "capacity", "status", "assigned_driver")

    def validate_plate(self, value: str) -> str:
        # Partial-unique at the DB level only covers active rows; mirror that here
        # for a clean 400 instead of an IntegrityError.
        qs = Bus.objects.filter(plate=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A bus with this plate already exists.", code="duplicate_plate"
            )
        return value


# ── Drivers (accounts.User rows with role=driver) ────────────────────────────
class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone", "is_verified", "created_at")
        read_only_fields = fields


class DriverWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "phone")

    def validate_email(self, value: str) -> str:
        value = value.lower()
        qs = User.objects.filter(email=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A user with this email already exists.", code="duplicate_email"
            )
        return value

    def create(self, validated_data):
        # Admin-created drivers are verified immediately (no email gate).
        return User.objects.create_user(role=User.Roles.DRIVER, is_verified=True, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


# ── Action payloads ──────────────────────────────────────────────────────────
class AssignDriverSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField()

    def validate_driver_id(self, value: int) -> int:
        exists = User.objects.filter(id=value, role=User.Roles.DRIVER, is_deleted=False).exists()
        if not exists:
            raise serializers.ValidationError(
                "No active driver with this id.", code="invalid_driver"
            )
        return value


class _StopEntrySerializer(serializers.Serializer):
    """One stop in an assign-stops payload — the BusStop write fields minus
    ``route`` (which is taken from the URL)."""

    name = serializers.CharField(max_length=120)
    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    sequence = serializers.IntegerField(min_value=0)


class AssignStopsSerializer(serializers.Serializer):
    """A list of stops to replace the route's existing stops. ``route`` comes
    from the URL, so it's intentionally absent from each entry."""

    stops = _StopEntrySerializer(many=True)


class MaintenanceSerializer(serializers.Serializer):
    """No required fields — the action simply flips the bus into maintenance."""

    note = serializers.CharField(required=False, allow_blank=True)
