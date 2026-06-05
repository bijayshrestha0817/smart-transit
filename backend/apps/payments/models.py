"""Domain models for ticketing, payments, and the passenger wallet (er-diagram §5).

All inherit ``TimeStampedSoftDeleteModel`` (timestamps + soft delete). Money is
``Decimal`` only (never float). Reference data is ``on_delete=PROTECT`` so financial
records can never dangle, while a ``Wallet``/``WalletTransaction`` cascades from its
owner. Per the diagram's conventions, ``qr_code`` and ``txn_ref`` carry partial unique
constraints ``WHERE is_deleted=false`` so soft-delete tombstones never block reuse.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedSoftDeleteModel

from .enums import PaymentGateway, PaymentStatus, TicketStatus, WalletTxnKind


class Ticket(TimeStampedSoftDeleteModel):
    """A passenger's purchased ride on a trip, carrying a signed QR token."""

    Status = TicketStatus  # enum lives in enums.py; aliased so Ticket.Status.X keeps working

    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets",
        limit_choices_to={"role": "passenger"},
    )
    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    # Signed token minted post-create (needs the pk); partial-unique while active.
    qr_code = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ISSUED)
    fare = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "tickets"
        indexes = [
            models.Index(fields=["passenger"]),
            models.Index(fields=["trip"]),
        ]
        constraints = [
            # Exclude the blank placeholder (set pre-mint at create time and on every
            # admin/import row) so "" is never uniqueness-bearing — otherwise a single
            # committed blank row, or a slow in-flight INSERT, would brick all issuance.
            models.UniqueConstraint(
                fields=["qr_code"],
                condition=Q(is_deleted=False) & ~Q(qr_code=""),
                name="uniq_ticket_qr_code_active",
            )
        ]

    def __str__(self) -> str:
        return f"Ticket #{self.pk} ({self.status})"


class Payment(TimeStampedSoftDeleteModel):
    """The financial record for a ticket — strictly 1:1 with its ``Ticket``."""

    Status = PaymentStatus  # aliased so Payment.Status.X keeps working
    Gateway = PaymentGateway

    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.PROTECT,
        related_name="payment",
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    gateway = models.CharField(max_length=12, choices=Gateway.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    # Idempotency key (minted internally this slice); partial-unique while active.
    txn_ref = models.CharField(max_length=64)

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "payments"
        indexes = [
            models.Index(fields=["gateway", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["txn_ref"],
                condition=Q(is_deleted=False),
                name="uniq_payment_txn_ref_active",
            )
        ]

    def __str__(self) -> str:
        return f"Payment #{self.pk} ({self.gateway}/{self.status})"


class Wallet(TimeStampedSoftDeleteModel):
    """A passenger's store-credit wallet — one per user, balance is source of truth."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "wallets"

    def __str__(self) -> str:
        return f"Wallet(user={self.user_id}, balance={self.balance})"


class WalletTransaction(TimeStampedSoftDeleteModel):
    """Append-only ledger row with a ``balance_after`` snapshot for audit."""

    Kind = WalletTxnKind  # aliased so WalletTransaction.Kind.X keeps working

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=64, blank=True)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_txns",
    )

    class Meta(TimeStampedSoftDeleteModel.Meta):
        db_table = "wallet_transactions"
        indexes = [
            models.Index(fields=["wallet", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount} -> {self.balance_after}"
