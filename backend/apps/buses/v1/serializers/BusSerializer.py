"""Bus serializers — read, write (with plate-uniqueness mirror), action payloads."""

from rest_framework import serializers

from apps.buses.models import Bus
from apps.buses.repository import BusRepository, DriverRepository


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
    # Declared plainly so the model's partial UniqueConstraint doesn't inject an auto
    # UniqueValidator — validate_plate owns the check and emits a stable code.
    plate = serializers.CharField(max_length=20)

    class Meta:
        model = Bus
        fields = ("plate", "capacity", "status", "assigned_driver")

    def validate_plate(self, value: str) -> str:
        exclude_pk = self.instance.pk if self.instance is not None else None
        if BusRepository.plate_exists(value, exclude_pk=exclude_pk):
            raise serializers.ValidationError(
                "A bus with this plate already exists.", code="duplicate_plate"
            )
        return value


class AssignDriverSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField()

    def validate_driver_id(self, value: int) -> int:
        if not DriverRepository.driver_exists(value):
            raise serializers.ValidationError(
                "No active driver with this id.", code="invalid_driver"
            )
        return value


class MaintenanceSerializer(serializers.Serializer):
    """No required fields — the action simply flips the bus into maintenance."""

    note = serializers.CharField(required=False, allow_blank=True)
