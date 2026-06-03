"""Stop endpoints — public reads, with an optional ?near proximity filter."""

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.buses.repository import BusStopRepository
from apps.buses.v1.serializers import BusStopSerializer


@extend_schema(tags=["stops"])
class StopListView(ListAPIView):
    """`GET /stops/` — list/search stops, optionally `?near=lat,lng&radius=` (public)."""

    serializer_class = BusStopSerializer
    permission_classes = [AllowAny]
    search_fields = ["name"]
    filterset_fields = ["route"]
    ordering_fields = ["name", "sequence", "created_at"]

    def get_queryset(self):
        qs = BusStopRepository.all_stops()
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
        return BusStopRepository.nearby(qs, lat, lng, radius)


@extend_schema(tags=["stops"])
class StopDetailView(RetrieveAPIView):
    """`GET /stops/{id}/` — stop detail (public)."""

    serializer_class = BusStopSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return BusStopRepository.all_stops()
