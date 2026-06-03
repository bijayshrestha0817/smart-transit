"""Driver admin endpoints — manage role=driver accounts (soft delete)."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.viewsets import ModelViewSet

from apps.buses.repository import DriverRepository
from apps.buses.v1.serializers import DriverSerializer, DriverWriteSerializer
from apps.buses.v1.service import DriverService
from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse


@extend_schema_view(
    list=extend_schema(tags=["admin-drivers"]),
    retrieve=extend_schema(tags=["admin-drivers"]),
    create=extend_schema(tags=["admin-drivers"]),
    update=extend_schema(tags=["admin-drivers"]),
    partial_update=extend_schema(tags=["admin-drivers"]),
    destroy=extend_schema(tags=["admin-drivers"]),
)
class AdminDriverViewSet(ModelViewSet):
    """`/admin/drivers/` — manage driver accounts (soft delete)."""

    permission_classes = [IsAdmin]
    search_fields = ["email", "full_name", "phone"]
    ordering_fields = ["email", "created_at"]

    def get_queryset(self):
        return DriverRepository.active_drivers()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return DriverWriteSerializer
        return DriverSerializer

    def create(self, request, *args, **kwargs):
        write = DriverWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        driver = DriverService.create_driver(write.validated_data)
        return CustomResponse(DriverSerializer(driver).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = DriverWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        driver = DriverService.update_driver(instance, write.validated_data)
        return CustomResponse(DriverSerializer(driver).data)
