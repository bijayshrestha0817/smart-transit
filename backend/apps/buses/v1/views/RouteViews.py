"""Route endpoints — public reads (generics) + admin CRUD (ViewSet).

Public reads use DRF generics (auto pagination/filtering, OpenAPI-friendly) with their
base queryset sourced from the repository. Admin mutations are explicit: validate →
service → CustomResponse.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

from apps.buses.repository import RouteRepository
from apps.buses.v1.serializers import (
    AssignStopsSerializer,
    BusStopSerializer,
    RouteDetailSerializer,
    RouteListSerializer,
    RouteWriteSerializer,
)
from apps.buses.v1.service import RouteService
from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse


# ── Public reads ─────────────────────────────────────────────────────────────
@extend_schema(tags=["routes"])
class RouteListView(ListAPIView):
    """`GET /routes/` — list/search routes (public)."""

    serializer_class = RouteListSerializer
    permission_classes = [AllowAny]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "estimated_duration"]

    def get_queryset(self):
        return RouteRepository.list_queryset()


@extend_schema(tags=["routes"])
class RouteDetailView(RetrieveAPIView):
    """`GET /routes/{id}/` — route detail with ordered stops + polyline (public)."""

    serializer_class = RouteDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return RouteRepository.detail_queryset()


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

    permission_classes = [IsAdmin]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "estimated_duration"]

    def get_queryset(self):
        # retrieve needs stops prefetched; list/update lookups don't.
        if self.action == "retrieve":
            return RouteRepository.detail_queryset()
        return RouteRepository.list_queryset()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RouteWriteSerializer
        if self.action == "retrieve":
            return RouteDetailSerializer
        return RouteListSerializer

    def create(self, request, *args, **kwargs):
        write = RouteWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        route = RouteService.create(write.validated_data)
        return CustomResponse(
            RouteDetailSerializer(RouteRepository.get_with_stops(route.id)).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        write = RouteWriteSerializer(instance, data=request.data, partial=partial)
        write.is_valid(raise_exception=True)
        RouteService.update(instance, write.validated_data)
        return CustomResponse(
            RouteDetailSerializer(RouteRepository.get_with_stops(instance.id)).data
        )

    @action(detail=True, methods=["post"], url_path="stops")
    def assign_stops(self, request, pk=None):
        """Replace this route's stops with the supplied ordered list."""
        route = self.get_object()
        serializer = AssignStopsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = RouteService.replace_stops(route, serializer.validated_data["stops"])
        return CustomResponse(
            BusStopSerializer(created, many=True).data, status=status.HTTP_201_CREATED
        )
