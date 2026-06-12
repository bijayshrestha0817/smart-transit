"""Passenger live tracking — active trips (with last position) on a given route, plus the
baseline per-trip ETA endpoint."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.views import APIView

from apps.common.permissions import IsPassenger
from apps.common.response import CustomResponse
from apps.trips.v1.serializers import ActiveTripSerializer, EtaSerializer
from apps.trips.v1.service import TripService


@extend_schema(
    tags=["trips"],
    parameters=[OpenApiParameter("route", int, required=True)],
    responses=ActiveTripSerializer(many=True),
)
class ActiveTripsView(APIView):
    """`GET /trips/active/?route={id}` — active trips on a route + last position."""

    permission_classes = [IsPassenger]

    def get(self, request, *args, **kwargs):
        route_id = request.query_params.get("route")
        if not route_id:
            raise ValidationError({"route": "This query parameter is required."}, code="required")
        active = TripService.active_on_route(route_id)
        return CustomResponse(ActiveTripSerializer(active, many=True).data)


@extend_schema(tags=["trips"], responses=EtaSerializer)
class TripEtaView(APIView):
    """`GET /trips/{id}/eta/` — baseline heuristic ETA to the next stop for one trip.

    404 only when no such trip exists; a real-but-untrackable trip returns an
    ``unavailable`` ETA (200), so the client can distinguish "gone" from "no fix yet".
    """

    permission_classes = [IsPassenger]

    def get(self, request, pk, *args, **kwargs):
        eta = TripService.eta_for_trip(pk)
        if eta is None:
            raise NotFound("No trip with this id.", code="not_found")
        return CustomResponse(EtaSerializer(eta).data)
