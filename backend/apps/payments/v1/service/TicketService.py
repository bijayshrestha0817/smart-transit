"""Ticket business logic — issue (with payment), refund (store credit), and reads.

``issue_ticket`` creates the Ticket (ISSUED) + its 1:1 Payment (PENDING) and mints a
signed QR token, all inside one ``transaction.atomic()``; for a WALLET purchase it then
settles synchronously (debit -> Payment SUCCESS -> Ticket ACTIVE), so an insufficient
balance rolls the WHOLE thing back (no ticket, no payment, no debit). ``refund_ticket``
credits store credit to the passenger's wallet and flips Payment+Ticket to REFUNDED.
Money is ``Decimal`` only; domain rules raise ``apps.payments.exceptions``.
"""

import uuid

from django.core.signing import dumps
from django.db import transaction

from apps.payments.enums import PaymentGateway, PaymentStatus, TicketStatus
from apps.payments.exceptions import (
    InvalidAmountError,
    InvalidTripForTicketError,
    TicketNotRefundableError,
)
from apps.payments.models import Ticket
from apps.payments.repository import PaymentRepository, TicketRepository
from apps.payments.v1.service.PaymentService import PaymentService
from apps.payments.v1.service.WalletService import WalletService
from apps.trips.enums import TripStatus

# A trip is sellable while it has not yet finished/been cancelled.
_SELLABLE_TRIP_STATUSES = {TripStatus.SCHEDULED, TripStatus.IN_PROGRESS}

QR_SALT = "ticket-qr"


def _mint_txn_ref() -> str:
    """Internally minted idempotency key for this slice (real provider ref is D4)."""
    return uuid.uuid4().hex


class TicketService:
    @staticmethod
    def issue_ticket(passenger, trip, gateway) -> Ticket:
        """Issue a ticket for ``trip`` to ``passenger``, paying via ``gateway``.

        Fare is server-authoritative (``trip.route.fare``); the client never sets price.
        WALLET settles inline; external gateways leave the payment PENDING for webhook
        confirmation. Fully atomic — a failed wallet debit persists nothing.
        """
        if trip is None or trip.status not in _SELLABLE_TRIP_STATUSES:
            raise InvalidTripForTicketError()

        fare = trip.route.fare
        if fare is None or fare <= 0:
            # Defence-in-depth: a free/negative snapshotted fare must never reach the
            # Ticket/Payment/debit path (a bad migration or seed could bypass the validator).
            raise InvalidAmountError("This trip has no valid fare configured.")
        with transaction.atomic():
            ticket = TicketRepository.create(
                {
                    "passenger": passenger,
                    "trip": trip,
                    "fare": fare,
                    "status": TicketStatus.ISSUED,
                }
            )
            # QR needs the pk, so sign + persist right after create (still pre-commit).
            ticket.qr_code = dumps(ticket.id, salt=QR_SALT)
            ticket.save(update_fields=["qr_code", "updated_at"])

            payment = PaymentRepository.create(
                {
                    "ticket": ticket,
                    "amount": fare,
                    "gateway": gateway,
                    "status": PaymentStatus.PENDING,
                    "txn_ref": _mint_txn_ref(),
                }
            )

            if gateway == PaymentGateway.WALLET:
                # Settle synchronously; insufficient balance rolls the whole block back.
                payment.ticket = ticket  # ensure the in-memory link for _settle_success
                PaymentService._settle_success(payment)

        # Re-read with select_related so the response serializer never queries.
        return TicketRepository.get_by_id(ticket.id)

    @staticmethod
    def refund_ticket(ticket: Ticket, by_user) -> Ticket:
        """Refund a SUCCESS payment as store credit to the passenger's wallet.

        Owner-or-admin is enforced at the view; the payment must be SUCCESS (else
        ``TicketNotRefundableError``), which also guards a second refund (idempotent).

        The SUCCESS check runs INSIDE the atomic block under a ``select_for_update`` lock on
        the Payment row (mirroring ``process_webhook``), so two concurrent refunds serialize:
        the second observes REFUNDED under the lock and raises rather than double-crediting.
        """
        with transaction.atomic():
            payment = PaymentRepository.by_ticket_for_update(ticket)
            if payment is None or payment.status != PaymentStatus.SUCCESS:
                raise TicketNotRefundableError()

            wallet = WalletService.get_or_create(ticket.passenger)
            WalletService.credit(
                wallet,
                payment.amount,
                reference=f"refund:{ticket.id}",
                payment=payment,
            )
            payment.status = PaymentStatus.REFUNDED
            payment.save(update_fields=["status", "updated_at"])
            ticket.status = TicketStatus.REFUNDED
            ticket.save(update_fields=["status", "updated_at"])

        return TicketRepository.get_by_id(ticket.id)

    @staticmethod
    def my_tickets(passenger, status=None):
        qs = TicketRepository.for_passenger(passenger)
        if status:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def get_for_user(ticket_id, user):
        """Fetch a ticket visible to ``user`` (owner, or any ticket for an admin).

        Returns ``None`` for a non-owned ticket so the view 404s rather than leaking
        the foreign ticket's existence (defence-in-depth alongside the view permission).
        """
        ticket = TicketRepository.get_by_id(ticket_id)
        if ticket is None:
            return None
        if getattr(user, "role", None) == "admin" or ticket.passenger_id == getattr(
            user, "id", None
        ):
            return ticket
        return None
