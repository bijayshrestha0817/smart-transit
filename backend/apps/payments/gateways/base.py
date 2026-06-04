"""Pluggable payment-gateway adapter interface + signature verifier.

A gateway adapter knows how to *start* a checkout for a pending payment and how to
*verify* an inbound webhook signature. The wallet adapter settles synchronously; the
external adapters (khalti/esewa/stripe) are stubs that raise
``GatewayNotConfiguredError`` until D4 wires real SDKs. ``verify_signature`` defaults
to accept (dev); real per-provider HMAC/secret verification is D4.
"""

from abc import ABC, abstractmethod


class BaseGateway(ABC):
    """Adapter contract — one concrete adapter per ``PaymentGateway`` value."""

    #: The ``PaymentGateway`` value this adapter serves.
    gateway: str = ""

    @abstractmethod
    def start_checkout(self, payment) -> dict:
        """Begin a gateway checkout for a PENDING payment.

        Returns a serializable dict (``checkout_ref`` etc.). Wallet settles inline and
        returns its terminal state; external adapters raise ``GatewayNotConfiguredError``.
        """
        raise NotImplementedError

    def verify_signature(self, txn_ref: str, status: str, signature: str | None) -> bool:
        """Verify an inbound webhook signature.

        Default = accept (dev). Real per-provider HMAC/secret verification is D4.
        """
        return True
