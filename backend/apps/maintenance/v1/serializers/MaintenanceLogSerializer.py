"""Maintenance log serializers — read (with bus_plate) and admin write."""

from rest_framework import serializers

from apps.buses.repository import BusRepository
from apps.maintenance.models import MaintenanceLog


class MaintenanceLogSerializer(serializers.ModelSerializer):
    """Read representation of a maintenance log."""

    bus_plate = serializers.CharField(source="bus.plate", read_only=True)

    class Meta:
        model = MaintenanceLog
        fields = (
            "id",
            "bus",
            "bus_plate",
            "service_type",
            "cost",
            "serviced_at",
            "next_due",
            "created_at",
        )
        read_only_fields = fields


class MaintenanceLogWriteSerializer(serializers.ModelSerializer):
    """Admin write payload — validates the bus against the repository.

    ``cost >= 0`` is enforced by the model's ``MinValueValidator`` (auto-mapped onto the
    serializer field, emitting the stable ``min_value`` code) — not duplicated here.
    """

    class Meta:
        model = MaintenanceLog
        fields = ("bus", "service_type", "cost", "serviced_at", "next_due")

    def validate_bus(self, value):
        if BusRepository.get_by_id(value.id) is None:
            raise serializers.ValidationError("No active bus with this id.", code="invalid_bus")
        return value
