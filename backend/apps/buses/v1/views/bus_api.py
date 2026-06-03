"""Bus admin endpoints — CRUD + assign-driver / maintenance actions."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet

from apps.buses.repository import BusRepository
from apps.buses.v1.serializers import (
    AssignDriverSerializer,
    BusSerializer,
    BusWriteSerializer,
    MaintenanceSerializer,
)
from apps.buses.v1.services import BusService
from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse


@extend_schema_view(
    list=extend_schema(tags=["admin-buses"]),
    retrieve=extend_schema(tags=["admin-buses"]),
    create=extend_schema(tags=["admin-buses"]),
    update=extend_schema(tags=["admin-buses"]),
    partial_update=extend_schema(tags=["admin-buses"]),
    destroy=extend_schema(tags=["admin-buses"]),
)
class AdminBusViewSet(ModelViewSet):
    """`/admin/buses/` — full CRUD (soft delete). Extra assign-driver / maintenance."""

    permission_classes = [IsAdmin]
    filterset_fields = ["status", "assigned_driver"]
    search_fields = ["plate"]
    ordering_fields = ["plate", "status", "created_at"]

    def get_queryset(self):
        return BusRepository.active()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return BusWriteSerializer
        return BusSerializer

    def create(self, request, *args, **kwargs):
        write = BusWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        bus = BusService.create(write.validated_data)
        return CustomResponse(BusSerializer(bus).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = BusWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        bus = BusService.update(instance, write.validated_data)
        return CustomResponse(BusSerializer(bus).data)

    @action(detail=True, methods=["patch"], url_path="assign-driver")
    def assign_driver(self, request, pk=None):
        bus = self.get_object()
        serializer = AssignDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bus = BusService.assign_driver(bus, serializer.validated_data["driver_id"])
        return CustomResponse(BusSerializer(bus).data)

    @action(detail=True, methods=["patch"], url_path="maintenance")
    def maintenance(self, request, pk=None):
        bus = self.get_object()
        serializer = MaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bus = BusService.set_maintenance(bus)
        return CustomResponse(BusSerializer(bus).data)
