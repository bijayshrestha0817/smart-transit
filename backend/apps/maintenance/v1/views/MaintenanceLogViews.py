"""Maintenance log admin endpoints — full CRUD (soft delete)."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse
from apps.maintenance.repository import MaintenanceLogRepository
from apps.maintenance.v1.serializers import (
    MaintenanceLogSerializer,
    MaintenanceLogWriteSerializer,
)
from apps.maintenance.v1.service import MaintenanceLogService


@extend_schema_view(
    list=extend_schema(tags=["admin-maintenance-logs"]),
    retrieve=extend_schema(tags=["admin-maintenance-logs"]),
    create=extend_schema(tags=["admin-maintenance-logs"]),
    update=extend_schema(tags=["admin-maintenance-logs"]),
    partial_update=extend_schema(tags=["admin-maintenance-logs"]),
    destroy=extend_schema(tags=["admin-maintenance-logs"]),
)
class AdminMaintenanceLogViewSet(ModelViewSet):
    """`/admin/maintenance-logs/` — full CRUD (soft delete)."""

    permission_classes = [IsAdmin]
    filterset_fields = ["bus"]
    ordering_fields = ["serviced_at", "cost", "created_at"]

    def get_queryset(self):
        return MaintenanceLogRepository.active()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MaintenanceLogWriteSerializer
        return MaintenanceLogSerializer

    def create(self, request, *args, **kwargs):
        write = MaintenanceLogWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        log = MaintenanceLogService.create(write.validated_data)
        return CustomResponse(MaintenanceLogSerializer(log).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = MaintenanceLogWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        log = MaintenanceLogService.update(instance, write.validated_data)
        return CustomResponse(MaintenanceLogSerializer(log).data)
