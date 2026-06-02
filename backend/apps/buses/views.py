"""Buses app views.

Public read endpoints (routes/stops) override the global ``IsAuthenticated`` with
``AllowAny``. Admin CRUD is gated by ``IsAdmin``. Views stay thin: validation
lives in serializers, multi-step mutations in ``services``. The response envelope
is applied automatically by the renderer/exception handler — views just return
``Response(serializer.data)`` (or use the generic mixins) and raise DRF errors.
"""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAdmin

from . import services
from .models import Bus, BusStop, Route
from .serializers import (
    AssignDriverSerializer,
    AssignStopsSerializer,
    BusSerializer,
    BusStopSerializer,
    BusWriteSerializer,
    DriverSerializer,
    DriverWriteSerializer,
    MaintenanceSerializer,
    RouteDetailSerializer,
    RouteListSerializer,
    RouteWriteSerializer,
)

User = get_user_model()


# ── Public reads ─────────────────────────────────────────────────────────────
@extend_schema(tags=["routes"])
class RouteListView(ListAPIView):
    """`GET /routes/` — list/search routes (public)."""

    queryset = Route.objects.all()
    serializer_class = RouteListSerializer
    permission_classes = [AllowAny]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "estimated_duration"]


@extend_schema(tags=["routes"])
class RouteDetailView(RetrieveAPIView):
    """`GET /routes/{id}/` — route detail with ordered stops + polyline (public)."""

    queryset = Route.objects.all()
    serializer_class = RouteDetailSerializer
    permission_classes = [AllowAny]


@extend_schema(tags=["stops"])
class StopListView(ListAPIView):
    """`GET /stops/` — list/search stops, optionally `?near=lat,lng&radius=` (public)."""

    queryset = BusStop.objects.all()
    serializer_class = BusStopSerializer
    permission_classes = [AllowAny]
    search_fields = ["name"]
    filterset_fields = ["route"]
    ordering_fields = ["name", "sequence", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        near = self.request.query_params.get("near")
        if not near:
            return qs
        try:
            lat_str, lng_str = near.split(",")
            lat = float(lat_str)
            lng = float(lng_str)
            radius = float(self.request.query_params.get("radius", "1.0"))
        except (ValueError, TypeError) as exc:
            raise ValidationError(
                {"near": "Expected `near=lat,lng` with an optional numeric `radius`."},
                code="invalid_near",
            ) from exc
        return services.nearby_stops(qs, lat, lng, radius)


@extend_schema(tags=["stops"])
class StopDetailView(RetrieveAPIView):
    """`GET /stops/{id}/` — stop detail (public)."""

    queryset = BusStop.objects.all()
    serializer_class = BusStopSerializer
    permission_classes = [AllowAny]


# ── Admin CRUD ───────────────────────────────────────────────────────────────
@extend_schema_view(
    list=extend_schema(tags=["admin-routes"]),
    retrieve=extend_schema(tags=["admin-routes"]),
    create=extend_schema(tags=["admin-routes"]),
    update=extend_schema(tags=["admin-routes"]),
    partial_update=extend_schema(tags=["admin-routes"]),
    destroy=extend_schema(tags=["admin-routes"]),
)
class AdminRouteViewSet(ModelViewSet):
    """`/admin/routes/` — full CRUD (soft delete). Extra `POST /{id}/stops/`."""

    queryset = Route.objects.all()
    permission_classes = [IsAdmin]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "estimated_duration"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RouteWriteSerializer
        if self.action == "retrieve":
            return RouteDetailSerializer
        return RouteListSerializer

    def create(self, request, *args, **kwargs):
        write = RouteWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        route = write.save()
        return Response(RouteDetailSerializer(route).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = RouteWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        route = write.save()
        return Response(RouteDetailSerializer(route).data)

    @action(detail=True, methods=["post"], url_path="stops")
    def assign_stops(self, request, pk=None):
        """Replace this route's stops with the supplied ordered list."""
        route = self.get_object()
        serializer = AssignStopsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = services.replace_route_stops(route, serializer.validated_data["stops"])
        return Response(BusStopSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(tags=["admin-buses"]),
    retrieve=extend_schema(tags=["admin-buses"]),
    create=extend_schema(tags=["admin-buses"]),
    update=extend_schema(tags=["admin-buses"]),
    partial_update=extend_schema(tags=["admin-buses"]),
    destroy=extend_schema(tags=["admin-buses"]),
)
class AdminBusViewSet(ModelViewSet):
    """`/admin/buses/` — full CRUD (soft delete). Extra assign-driver/maintenance."""

    queryset = Bus.objects.select_related("assigned_driver")
    permission_classes = [IsAdmin]
    filterset_fields = ["status", "assigned_driver"]
    search_fields = ["plate"]
    ordering_fields = ["plate", "status", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return BusWriteSerializer
        return BusSerializer

    def create(self, request, *args, **kwargs):
        write = BusWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        bus = write.save()
        return Response(BusSerializer(bus).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = BusWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        bus = write.save()
        return Response(BusSerializer(bus).data)

    @action(detail=True, methods=["patch"], url_path="assign-driver")
    def assign_driver(self, request, pk=None):
        bus = self.get_object()
        serializer = AssignDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bus = services.assign_driver(bus, serializer.validated_data["driver_id"])
        return Response(BusSerializer(bus).data)

    @action(detail=True, methods=["patch"], url_path="maintenance")
    def maintenance(self, request, pk=None):
        bus = self.get_object()
        serializer = MaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bus = services.set_maintenance(bus)
        return Response(BusSerializer(bus).data)


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

    # ``User.objects`` (UserManager) does NOT exclude soft-deleted rows, so filter
    # explicitly to keep deleted drivers out of the admin list.
    queryset = User.objects.filter(role=User.Roles.DRIVER, is_deleted=False)
    permission_classes = [IsAdmin]
    search_fields = ["email", "full_name", "phone"]
    ordering_fields = ["email", "created_at"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return DriverWriteSerializer
        return DriverSerializer

    def create(self, request, *args, **kwargs):
        write = DriverWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        driver = write.save()
        return Response(DriverSerializer(driver).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = DriverWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        driver = write.save()
        return Response(DriverSerializer(driver).data)
