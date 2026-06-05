"""Passenger wallet — balance summary + the append-only ledger (cursor paged)."""

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView

from apps.common.permissions import IsPassenger
from apps.common.response import CustomResponse
from apps.payments.v1.serializers import WalletSerializer, WalletTransactionSerializer
from apps.payments.v1.service import WalletService


@extend_schema(tags=["wallet"], responses=WalletSerializer)
class WalletBalanceView(APIView):
    """`GET /wallet/` — the passenger's current store-credit balance."""

    permission_classes = [IsPassenger]

    def get(self, request, *args, **kwargs):
        balance = WalletService.balance(request.user)
        return CustomResponse(WalletSerializer({"balance": balance}).data)


@extend_schema(tags=["wallet"])
class WalletTransactionsView(ListAPIView):
    """`GET /wallet/transactions/` — the passenger's ledger (cursor paginated)."""

    serializer_class = WalletTransactionSerializer
    permission_classes = [IsPassenger]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        # Schema generation has no request user — the service returns the empty ledger qs
        # for a None/anonymous user, so drf-spectacular derives the model without the view
        # ever touching the ORM (all data access stays in the service/repository layer).
        if getattr(self, "swagger_fake_view", False):
            return WalletService.ledger(None)
        return WalletService.ledger(self.request.user)
