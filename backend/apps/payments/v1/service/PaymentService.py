"""Payment business logic — gateway checkout + idempotent webhook settlement.

Settlement (``_settle_success``) is the single place that moves a payment to SUCCESS
and its ticket to ACTIVE; it is idempotent (a second call on an already-SUCCESS payment
is a no-op). ``process_webhook`` locks the payment row ``FOR UPDATE`` so a duplicate
webhook with the same ``txn_ref`` serializes behind the first, observes its terminal
state, and returns unchanged — no second debit, no second ledger row, no double
transition. Money is ``Decimal`` only; all mutations run inside ``transaction.atomic()``.
"""

from django.db import transaction

from apps.payments.enums import PaymentGateway, PaymentStatus, TicketStatus
from apps.payments.exceptions import PaymentFailedError
from apps.payments.gateways import get_gateway
from apps.payments.models import Payment
from apps.payments.repository import PaymentRepository

# Statuses from which a payment can no longer change state.
_TERMINAL = {PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.REFUNDED}


class PaymentService:
    @staticmethod
    def _settle_success(payment: Payment) -> Payment:
        """Move ``payment`` to SUCCESS and its ticket to ACTIVE. Idempotent.

        For a WALLET payment, debit the passenger's wallet first (raises
        ``InsufficientBalanceError`` if short, rolling back the caller's atomic block).
        Must be called inside ``transaction.atomic()`` by the caller.
        """
        if payment.status == PaymentStatus.SUCCESS:
            return payment  # already settled — no-op (idempotency guard)

        if payment.gateway == PaymentGateway.WALLET:
            # Local import avoids an import cycle (PaymentService <-> WalletService).
            from apps.payments.v1.service.WalletService import WalletService

            wallet = WalletService.get_or_create(payment.ticket.passenger)
            WalletService.debit(
                wallet,
                payment.amount,
                reference=f"ticket:{payment.ticket_id}",
                payment=payment,
            )

        payment.status = PaymentStatus.SUCCESS
        payment.save(update_fields=["status", "updated_at"])

        ticket = payment.ticket
        ticket.status = TicketStatus.ACTIVE
        ticket.save(update_fields=["status", "updated_at"])
        return payment

    @staticmethod
    def checkout(ticket, by_user) -> dict:
        """Start a gateway checkout for the ticket's PENDING payment.

        WALLET payments are already settled at issue time, so the adapter just reports
        their terminal state. External adapters raise ``GatewayNotConfiguredError`` (D4).
        """
        payment = PaymentRepository.by_ticket(ticket)
        if payment is None:
            raise PaymentFailedError("No payment exists for this ticket.")
        gateway = get_gateway(payment.gateway)
        return gateway.start_checkout(payment)

    @staticmethod
    def process_webhook(gateway, txn_ref, status, signature=None) -> Payment:
        """Confirm a payment from a gateway webhook — idempotent on ``txn_ref``.

        A duplicate webhook serializes behind the first under the row lock and, finding
        the payment already terminal, returns it unchanged (no double settlement).
        """
        adapter = get_gateway(gateway)
        if not adapter.verify_signature(txn_ref, status, signature):
            raise PaymentFailedError("Webhook signature verification failed.")

        with transaction.atomic():
            payment = PaymentRepository.by_txn_ref_for_update(txn_ref)
            if payment is None:
                raise PaymentFailedError("No payment matches this transaction reference.")

            if payment.status in _TERMINAL:
                return payment  # idempotent no-op — already in a final state

            if status == PaymentStatus.SUCCESS:
                return PaymentService._settle_success(payment)

            if status == PaymentStatus.FAILED:
                payment.status = PaymentStatus.FAILED
                payment.save(update_fields=["status", "updated_at"])
                ticket = payment.ticket
                ticket.status = TicketStatus.CANCELLED
                ticket.save(update_fields=["status", "updated_at"])
                return payment

            raise PaymentFailedError("Unsupported webhook status.")
