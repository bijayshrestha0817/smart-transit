"""Driver log + SOS endpoints (v1), mounted at /api/v1/.

Both are ``IsDriver``: ``request.user`` is the reporting driver. Views validate the
payload, delegate to ``DriverLogService`` (which owns all ORM + the SOS fan-out), and
build a 201 ``CustomResponse`` from the created log. Views NEVER touch the ORM.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.permissions import IsDriver
from apps.common.response import CustomResponse
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.v1.serializers import (
    CreateDriverLogSerializer,
    DriverLogSerializer,
    SosSerializer,
)
from apps.driver_logs.v1.service import DriverLogService


@extend_schema(
    tags=["driver-logs"],
    request=CreateDriverLogSerializer,
    responses=DriverLogSerializer,
)
class DriverLogCreateView(APIView):
    """`POST /driver/logs/` — record a delay/breakdown/fuel/note (or sos) log."""

    permission_classes = [IsDriver]

    def post(self, request, *args, **kwargs):
        serializer = CreateDriverLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        log = DriverLogService.create_log(
            request.user,
            event_type=data["event_type"],
            notes=data.get("notes", ""),
            trip=data.get("trip"),
        )
        return CustomResponse(DriverLogSerializer(log).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["driver-logs"],
    request=SosSerializer,
    responses=DriverLogSerializer,
)
class DriverSosView(APIView):
    """`POST /driver/sos/` — SOS: a log (event_type=sos) + alerts broadcast + EMERGENCY
    notifications. The committed log is the audit record; fan-out is best-effort, so a
    degraded broadcast/notify still returns 201."""

    permission_classes = [IsDriver]

    def post(self, request, *args, **kwargs):
        serializer = SosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        log = DriverLogService.create_log(
            request.user,
            event_type=DriverLogEventType.SOS,
            notes=data.get("notes", ""),
            trip=data.get("trip"),
        )
        return CustomResponse(DriverLogSerializer(log).data, status=status.HTTP_201_CREATED)
