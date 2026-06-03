"""Admin fleet snapshot — all active trips + last position (seed for the live map)."""

from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse
from apps.trips.v1.serializers import ActiveTripSerializer
from apps.trips.v1.service import TripService


@extend_schema(tags=["admin-fleet"], responses=ActiveTripSerializer(many=True))
class FleetSnapshotView(APIView):
    """`GET /admin/fleet/` — every IN_PROGRESS trip + its last position."""

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        snapshot = TripService.fleet_snapshot()
        return CustomResponse(ActiveTripSerializer(snapshot, many=True).data)
