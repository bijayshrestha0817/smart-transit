"""Admin alerts feed (v1), mounted at /api/v1/.

Both endpoints are ``IsAdmin``: the incident log is an operator surface. The feed is the
cursor-paged seed the frontend loads before the ``/ws/alerts/`` live stream takes over;
acknowledge clears an open incident. Views build ``CustomResponse``; the service owns ORM.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView

from apps.alerts.enums import AlertSeverity, AlertStatus
from apps.alerts.repository import AlertRepository
from apps.alerts.v1.serializers import AlertSerializer
from apps.alerts.v1.service import AlertService
from apps.common.permissions import IsAdmin
from apps.common.response import CustomResponse


@extend_schema(
    tags=["alerts"],
    parameters=[
        OpenApiParameter("status", str, enum=[s.value for s in AlertStatus], required=False),
        OpenApiParameter("severity", str, enum=[s.value for s in AlertSeverity], required=False),
    ],
    responses=AlertSerializer(many=True),
)
class AlertFeedView(ListAPIView):
    """`GET /admin/alerts/?status=open&severity=critical` — the incident log (cursor)."""

    permission_classes = [IsAdmin]
    serializer_class = AlertSerializer

    def get_queryset(self):
        # No request user during schema generation — return an empty, well-typed queryset.
        if getattr(self, "swagger_fake_view", False):
            return AlertService.feed()
        params = self.request.query_params
        return AlertService.feed(
            status=params.get("status") or None,
            severity=params.get("severity") or None,
        )


@extend_schema(tags=["alerts"], request=None, responses=AlertSerializer)
class AlertAcknowledgeView(APIView):
    """`POST /admin/alerts/{id}/acknowledge/` — mark an alert acknowledged (idempotent)."""

    permission_classes = [IsAdmin]

    def post(self, request, pk, *args, **kwargs):
        alert = AlertRepository.get_by_id(pk)
        if alert is None:
            raise NotFound("No alert with this id.", code="not_found")
        alert = AlertService.acknowledge(alert, request.user)
        return CustomResponse(AlertSerializer(alert).data)
