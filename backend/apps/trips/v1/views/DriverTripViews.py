"""Driver trip lifecycle — list/retrieve own trips + start / end / passenger-count / gps batch.

The queryset is scoped to the requesting driver, so ``get_object`` 404s on trips the
driver doesn't own and ``list`` only ever returns the driver's own trips. The service
ALSO re-asserts the driver as a defence-in-depth check.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin

from apps.common.permissions import IsDriver
from apps.common.response import CustomResponse
from apps.trips.repository import TripRepository
from apps.trips.v1.serializers import (
    GpsBatchSerializer,
    PassengerCountSerializer,
    TripSerializer,
)
from apps.trips.v1.service import TripService


@extend_schema_view(
    list=extend_schema(tags=["driver-trips"]),
    retrieve=extend_schema(tags=["driver-trips"]),
)
class DriverTripViewSet(ListModelMixin, RetrieveModelMixin, viewsets.GenericViewSet):
    """`/driver/trips/` (list own) + `/driver/trips/{id}/` (retrieve) + lifecycle actions."""

    permission_classes = [IsDriver]
    serializer_class = TripSerializer
    # The driver discovers their own assigned trips here; `?status=` narrows by lifecycle
    # state (e.g. scheduled vs in_progress). Same global cursor pagination as the admin list.
    filterset_fields = ["status"]
    ordering_fields = ["status", "start_time", "created_at"]

    def get_queryset(self):
        # During schema generation there's no request user — return the base queryset
        # so drf-spectacular can still derive the path-parameter type from the model.
        if getattr(self, "swagger_fake_view", False):
            return TripRepository.active()
        return TripRepository.active().filter(driver=self.request.user)

    @extend_schema(tags=["driver-trips"], request=None, responses=TripSerializer)
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        trip = self.get_object()
        trip = TripService.start_trip(trip, request.user)
        return CustomResponse(TripSerializer(trip).data)

    @extend_schema(tags=["driver-trips"], request=None, responses=TripSerializer)
    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request, pk=None):
        trip = self.get_object()
        trip = TripService.end_trip(trip, request.user)
        return CustomResponse(TripSerializer(trip).data)

    @extend_schema(
        tags=["driver-trips"], request=PassengerCountSerializer, responses=TripSerializer
    )
    @action(detail=True, methods=["post"], url_path="passenger-count")
    def passenger_count(self, request, pk=None):
        trip = self.get_object()
        serializer = PassengerCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trip = TripService.set_passenger_count(
            trip, request.user, serializer.validated_data["count"]
        )
        return CustomResponse(TripSerializer(trip).data)

    @extend_schema(tags=["driver-trips"], request=GpsBatchSerializer)
    @action(detail=True, methods=["post"], url_path="gps/batch")
    def gps_batch(self, request, pk=None):
        trip = self.get_object()
        serializer = GpsBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = TripService.ingest_gps(trip, request.user, serializer.validated_data["points"])
        return CustomResponse({"count": count}, status=status.HTTP_202_ACCEPTED)
