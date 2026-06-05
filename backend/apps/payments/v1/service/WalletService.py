"""Wallet business logic — store-credit balance + append-only ledger.

Balance is the source of truth on the ``Wallet`` row and is mutated ONLY under
``select_for_update`` (``WalletRepository.get_for_update``), so concurrent debits/credits
serialize. Every balance move writes a ledger row carrying a ``balance_after`` snapshot,
inside the same ``transaction.atomic()`` as the balance save. Money is ``Decimal`` only,
quantized to 2dp — never float.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.payments.enums import WalletTxnKind
from apps.payments.exceptions import InsufficientBalanceError, InvalidAmountError
from apps.payments.models import Wallet, WalletTransaction
from apps.payments.repository import WalletRepository

TWO_PLACES = Decimal("0.01")


def _q(amount) -> Decimal:
    """Coerce to ``Decimal`` and quantize to 2dp (half-up) — the money invariant."""
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class WalletService:
    @staticmethod
    def get_or_create(user) -> Wallet:
        return WalletRepository.get_or_create(user)

    @staticmethod
    def balance(user) -> Decimal:
        wallet = WalletRepository.get_for_user(user)
        return wallet.balance if wallet is not None else Decimal("0.00")

    @staticmethod
    def ledger(user):
        """Queryset of the user's ledger rows (for the cursor pager).

        Returns the empty ledger queryset when there is no real wallet — including a
        None/anonymous user (e.g. drf-spectacular schema generation), so views never need
        to reach for the ORM themselves.
        """
        if user is None or not getattr(user, "is_authenticated", False):
            return WalletTransaction.objects.none()
        wallet = WalletRepository.get_for_user(user)
        if wallet is None:
            return WalletTransaction.objects.none()
        return WalletRepository.ledger(wallet)

    @staticmethod
    def debit(wallet: Wallet, amount, reference="", payment=None) -> WalletTransaction:
        """Debit ``amount`` from ``wallet`` under a row lock; raise if short.

        Re-reads the wallet ``FOR UPDATE`` so the balance check + decrement are atomic
        against concurrent writers. Caller is responsible for the surrounding atomic block.
        """
        amount = _q(amount)
        if amount <= 0:
            # A non-positive debit would invert into a credit — reject before any write.
            raise InvalidAmountError()
        with transaction.atomic():
            locked = WalletRepository.get_for_update(wallet.user)
            if amount > locked.balance:
                raise InsufficientBalanceError()
            locked.balance = _q(locked.balance - amount)
            locked.save(update_fields=["balance", "updated_at"])
            txn = WalletRepository.create_txn(
                {
                    "wallet": locked,
                    "kind": WalletTxnKind.DEBIT,
                    "amount": amount,
                    "balance_after": locked.balance,
                    "reference": reference,
                    "payment": payment,
                }
            )
        return txn

    @staticmethod
    def credit(wallet: Wallet, amount, reference="", payment=None) -> WalletTransaction:
        """Credit ``amount`` to ``wallet`` under a row lock and append a ledger row."""
        amount = _q(amount)
        if amount <= 0:
            # A non-positive credit is meaningless / would silently drain the wallet.
            raise InvalidAmountError()
        with transaction.atomic():
            locked = WalletRepository.get_for_update(wallet.user)
            locked.balance = _q(locked.balance + amount)
            locked.save(update_fields=["balance", "updated_at"])
            txn = WalletRepository.create_txn(
                {
                    "wallet": locked,
                    "kind": WalletTxnKind.CREDIT,
                    "amount": amount,
                    "balance_after": locked.balance,
                    "reference": reference,
                    "payment": payment,
                }
            )
        return txn
