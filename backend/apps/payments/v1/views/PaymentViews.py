"""Payment endpoints — passenger checkout + the gateway webhook (idempotent).

``/payments/checkout/`` starts a gateway checkout for the caller's own pending payment.
``/payments/webhook/{gateway}/`` is called by the gateway server (no cookie), so it is
``AllowAny`` + ``AnonRateThrottle`` and confirms idempotently on ``txn_ref``. Both
delegate to the service layer and build the ``{data, meta, errors}`` envelope.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.common.permissions import IsPassenger
from apps.common.response import CustomResponse
from apps.payments.enums import PaymentGateway
from apps.payments.v1.serializers import (
    CheckoutResponseSerializer,
    CheckoutSerializer,
    WebhookResponseSerializer,
    WebhookSerializer,
)
from apps.payments.v1.service import PaymentService, TicketService


@extend_schema(tags=["payments"], request=CheckoutSerializer, responses=CheckoutResponseSerializer)
class CheckoutView(APIView):
    """`POST /payments/checkout/` — start a gateway payment for an owned ticket."""

    permission_classes = [IsPassenger]

    def post(self, request, *args, **kwargs):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = TicketService.get_for_user(serializer.validated_data["ticket"], request.user)
        # Scope to the caller's own ticket — never leak another passenger's payment.
        if ticket is None or ticket.passenger_id != request.user.id:
            raise NotFound("No ticket with this id.")
        result = PaymentService.checkout(ticket, request.user)
        return CustomResponse(result)


@extend_schema(tags=["payments"], request=WebhookSerializer, responses=WebhookResponseSerializer)
class WebhookView(APIView):
    """`POST /payments/webhook/{gateway}/` — gateway confirmation, idempotent on txn_ref."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [AnonRateThrottle]

    def post(self, request, gateway=None, *args, **kwargs):
        if gateway not in PaymentGateway.values:
            raise ValidationError({"gateway": "Unknown gateway."}, code="invalid_gateway")
        serializer = WebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment = PaymentService.process_webhook(
            gateway,
            data["txn_ref"],
            data["status"],
            data.get("signature"),
        )
        return CustomResponse(
            {
                "txn_ref": payment.txn_ref,
                "status": payment.status,
                "ticket_status": payment.ticket.status,
                "ticket": payment.ticket_id,
            }
        )
