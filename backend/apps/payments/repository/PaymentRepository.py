"""Data access for Payment. All Payment ORM lives here."""

from apps.common.repository import BaseRepository
from apps.payments.models import Payment


class PaymentRepository(BaseRepository):
    model = Payment

    @classmethod
    def active(cls):
        return Payment.objects.select_related("ticket", "ticket__passenger")

    @classmethod
    def by_txn_ref(cls, txn_ref):
        return cls.active().filter(txn_ref=txn_ref).first()

    @classmethod
    def by_txn_ref_for_update(cls, txn_ref):
        """Row-locked variant — webhook settlement reads under ``select_for_update``
        so a duplicate webhook serializes behind the first and observes its result."""
        return (
            Payment.objects.select_related("ticket")
            .select_for_update()
            .filter(txn_ref=txn_ref)
            .first()
        )

    @classmethod
    def by_ticket(cls, ticket):
        return cls.active().filter(ticket=ticket).first()

    @classmethod
    def by_ticket_for_update(cls, ticket):
        """Row-locked variant — refund settlement reads under ``select_for_update`` so a
        duplicate refund serializes behind the first and observes its terminal state."""
        return (
            Payment.objects.select_related("ticket")
            .select_for_update()
            .filter(ticket=ticket)
            .first()
        )

    @classmethod
    def create(cls, data: dict) -> Payment:
        return Payment.objects.create(**data)
