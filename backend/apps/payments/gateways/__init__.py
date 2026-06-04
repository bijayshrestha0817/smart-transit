"""Gateway adapter registry — resolve a ``PaymentGateway`` value to its adapter."""

from apps.payments.enums import PaymentGateway

from .base import BaseGateway
from .external import EsewaGateway, KhaltiGateway, StripeGateway
from .wallet import WalletGateway

_REGISTRY: dict[str, BaseGateway] = {
    PaymentGateway.WALLET: WalletGateway(),
    PaymentGateway.KHALTI: KhaltiGateway(),
    PaymentGateway.ESEWA: EsewaGateway(),
    PaymentGateway.STRIPE: StripeGateway(),
}


def get_gateway(gateway: str) -> BaseGateway:
    """Return the adapter for ``gateway`` (a ``PaymentGateway`` value)."""
    return _REGISTRY[gateway]


__all__ = [
    "BaseGateway",
    "EsewaGateway",
    "KhaltiGateway",
    "StripeGateway",
    "WalletGateway",
    "get_gateway",
]
