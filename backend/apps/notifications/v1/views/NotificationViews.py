"""Notification feed + read endpoints (v1), mounted at /api/v1/.

All three are ``IsAuthenticated`` (any role) and strictly owner-scoped: the queryset
is filtered to ``request.user`` so a user can never read or mark another user's
notification (a foreign id 404s — no IDOR). Views build ``CustomResponse``; the
service owns all ORM.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.response import CustomResponse
from apps.notifications.v1.serializers import (
    NotificationSerializer,
    ReadAllResponseSerializer,
)
from apps.notifications.v1.service import NotificationService


@extend_schema(
    tags=["notifications"],
    parameters=[OpenApiParameter("unread", bool, required=False)],
    responses=NotificationSerializer(many=True),
)
class NotificationFeedView(ListAPIView):
    """`GET /notifications/?unread=true` — the requester's notification feed (cursor)."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        # No request user during schema generation — return an empty queryset.
        if getattr(self, "swagger_fake_view", False):
            return NotificationService.feed(None)
        unread_only = self.request.query_params.get("unread") in ("true", "1")
        return NotificationService.feed(self.request.user, unread_only=unread_only)


@extend_schema(tags=["notifications"], request=None, responses=NotificationSerializer)
class NotificationReadView(APIView):
    """`POST /notifications/{id}/read/` — mark one notification read (owner-scoped, idempotent)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        notification = NotificationService.feed(request.user).filter(id=pk).first()
        if notification is None:
            raise NotFound()
        notification = NotificationService.mark_read(notification)
        return CustomResponse(NotificationSerializer(notification).data)


@extend_schema(tags=["notifications"], request=None, responses=ReadAllResponseSerializer)
class NotificationReadAllView(APIView):
    """`POST /notifications/read-all/` — mark all the requester's notifications read."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        updated = NotificationService.mark_all_read(request.user)
        return CustomResponse({"updated": updated})
