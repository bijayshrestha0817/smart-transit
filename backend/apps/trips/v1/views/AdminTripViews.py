"""Admin trip scheduling — minimal CRUD (soft delete) so trips exist to drive."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse
from apps.trips.repository import TripRepository
from apps.trips.v1.serializers import AdminTripWriteSerializer, TripSerializer
from apps.trips.v1.service import TripService


@extend_schema_view(
    list=extend_schema(tags=["admin-trips"]),
    retrieve=extend_schema(tags=["admin-trips"]),
    create=extend_schema(tags=["admin-trips"]),
    update=extend_schema(tags=["admin-trips"]),
    partial_update=extend_schema(tags=["admin-trips"]),
    destroy=extend_schema(tags=["admin-trips"]),
)
class AdminTripViewSet(ModelViewSet):
    """`/admin/trips/` — full CRUD (soft delete) for scheduling trips."""

    permission_classes = [IsAdmin]
    filterset_fields = ["status", "route", "bus", "driver"]
    search_fields = ["bus__plate", "route__name", "driver__email"]
    ordering_fields = ["status", "start_time", "created_at"]

    def get_queryset(self):
        return TripRepository.active()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AdminTripWriteSerializer
        return TripSerializer

    def create(self, request, *args, **kwargs):
        write = AdminTripWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        trip = TripService.create(write.validated_data)
        return CustomResponse(TripSerializer(trip).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = AdminTripWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        trip = TripService.update(instance, write.validated_data)
        return CustomResponse(TripSerializer(trip).data)
