"""Domain exceptions for the payments app (build on the shared CustomException)."""

from apps.common.exceptions import CustomException


class InsufficientBalanceError(CustomException):
    def __init__(self):
        super().__init__(
            message="Your wallet balance is insufficient for this purchase.",
            status=400,
            code="insufficient_balance",
        )


class InvalidAmountError(CustomException):
    """A non-positive amount reached the money path (negative/zero fare, debit, or credit)."""

    def __init__(self, message="The amount must be a positive value."):
        super().__init__(
            message=message,
            status=400,
            code="invalid_amount",
        )


class PaymentFailedError(CustomException):
    def __init__(self, message="The payment could not be processed."):
        super().__init__(
            message=message,
            status=400,
            code="payment_failed",
        )


class GatewayNotConfiguredError(CustomException):
    """Raised by external adapter stubs until D4 wires real provider SDKs."""

    def __init__(self):
        super().__init__(
            message="This payment gateway is not configured yet.",
            status=400,
            code="gateway_not_configured",
        )


class TicketNotRefundableError(CustomException):
    def __init__(self):
        super().__init__(
            message="This ticket cannot be refunded.",
            status=409,
            code="ticket_not_refundable",
        )


class InvalidTripForTicketError(CustomException):
    def __init__(self):
        super().__init__(
            message="This trip is not available for ticket purchase.",
            status=400,
            code="invalid_trip",
        )
