"""Passenger ticketing — list/issue own tickets, retrieve (owner/admin), refund.

The list/retrieve querysets are scoped to the requesting passenger via the service, so
``retrieve`` 404s on tickets the passenger doesn't own (admins pass via owner-or-admin).
Money mutations go through the service layer; views only validate, delegate, and build
the ``{data, meta, errors}`` envelope — never touching the ORM.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import IsPassenger
from apps.common.response import CustomResponse
from apps.payments.v1.serializers import (
    IssueTicketSerializer,
    RefundSerializer,
    TicketSerializer,
)
from apps.payments.v1.service import TicketService


@extend_schema_view(
    list=extend_schema(tags=["tickets"]),
    retrieve=extend_schema(tags=["tickets"]),
    create=extend_schema(tags=["tickets"], request=IssueTicketSerializer),
)
class TicketViewSet(viewsets.GenericViewSet):
    """`/tickets/` (list/issue own) + `/tickets/{id}/` (detail) + `/tickets/{id}/refund/`."""

    serializer_class = TicketSerializer
    # ``status`` narrows the list by lifecycle state (issued/active/refunded/…).
    filterset_fields = ["status"]
    ordering_fields = ["status", "created_at"]

    def get_permissions(self):
        # retrieve is owner-or-admin (ownership scoped in the service -> 404 if foreign);
        # everything else (list/issue/refund) is passenger-only.
        if self.action == "retrieve":
            return [IsAuthenticated()]
        return [IsPassenger()]

    def get_queryset(self):
        # During schema generation there's no request user — return an empty base qs.
        if getattr(self, "swagger_fake_view", False):
            return TicketService.my_tickets(None)
        status_param = self.request.query_params.get("status")
        return TicketService.my_tickets(self.request.user, status_param)

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        serializer = TicketSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        # Service scopes to owner-or-admin; a foreign ticket returns None -> 404.
        ticket = TicketService.get_for_user(kwargs["pk"], request.user)
        if ticket is None:
            raise NotFound("No ticket with this id.")
        return CustomResponse(TicketSerializer(ticket).data)

    @extend_schema(tags=["tickets"], request=IssueTicketSerializer, responses=TicketSerializer)
    def create(self, request, *args, **kwargs):
        serializer = IssueTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trip = serializer.context["trip_obj"]
        ticket = TicketService.issue_ticket(
            request.user, trip, serializer.validated_data["gateway"]
        )
        return CustomResponse(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["tickets"], request=RefundSerializer, responses=TicketSerializer)
    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        # IsPassenger gates the request; the service scopes to the owner (foreign -> 404).
        ticket = TicketService.get_for_user(pk, request.user)
        if ticket is None:
            raise NotFound("No ticket with this id.")
        ticket = TicketService.refund_ticket(ticket, request.user)
        return CustomResponse(TicketSerializer(ticket).data)
