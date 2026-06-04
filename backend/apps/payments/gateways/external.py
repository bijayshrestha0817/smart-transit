"""External provider adapter STUBS (Khalti / eSewa / Stripe).

These are deliberately inert for the gateway-agnostic slice: ``start_checkout`` raises
``GatewayNotConfiguredError`` (code ``gateway_not_configured``, 400) until D4 wires the
real provider SDKs + redirect/checkout-session creation. Webhook signature verification
inherits the dev-accept default from ``BaseGateway``; real per-provider HMAC/secret
verification is also D4.
"""

from apps.payments.enums import PaymentGateway
from apps.payments.exceptions import GatewayNotConfiguredError

from .base import BaseGateway


class _ExternalGateway(BaseGateway):
    """Shared stub: cannot start a real checkout in this slice."""

    def start_checkout(self, payment) -> dict:
        raise GatewayNotConfiguredError()


class KhaltiGateway(_ExternalGateway):
    gateway = PaymentGateway.KHALTI


class EsewaGateway(_ExternalGateway):
    gateway = PaymentGateway.ESEWA


class StripeGateway(_ExternalGateway):
    gateway = PaymentGateway.STRIPE
