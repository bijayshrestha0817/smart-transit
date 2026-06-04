"""Payments endpoints (v1), mounted at /api/v1/.

DefaultRouter handles the ticket ViewSet (list/issue/retrieve + refund action); plain
``path()`` handles the wallet reads and the payment checkout/webhook APIViews. The
webhook carries a ``{gateway}`` path segment so the right adapter verifies the signature.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CheckoutView,
    TicketViewSet,
    WalletBalanceView,
    WalletTransactionsView,
    WebhookView,
)

app_name = "payments"

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("wallet/", WalletBalanceView.as_view(), name="wallet-balance"),
    path("wallet/transactions/", WalletTransactionsView.as_view(), name="wallet-transactions"),
    path("payments/checkout/", CheckoutView.as_view(), name="payments-checkout"),
    path("payments/webhook/<str:gateway>/", WebhookView.as_view(), name="payments-webhook"),
    *router.urls,
]
