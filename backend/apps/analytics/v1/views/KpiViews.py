"""Admin KPI overview — operations command-center cards (single computed object)."""

from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.analytics.v1.serializers import KpiSerializer
from apps.analytics.v1.service import KpiService
from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse


@extend_schema(tags=["admin-analytics"], responses=KpiSerializer)
class KpiOverviewView(APIView):
    """`GET /admin/overview/kpis/` — admin KPI cards.

    Live aggregation across the fleet/trip/ticket/payment/driver-log/maintenance tables.
    Two semantic choices worth noting:

    * ``active_buses`` = distinct buses on an IN_PROGRESS trip (FleetSnapshot semantics),
      which is distinct from ``buses_active`` = ``Bus.status == active`` fleet composition.
    * ``avg_delay`` = average over today's COMPLETED trips of
      ``max(0, (end_time - start_time) minutes - route.estimated_duration)``; ``null`` when
      there are no completed trips today.
    """

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        return CustomResponse(KpiSerializer(KpiService.overview()).data)
