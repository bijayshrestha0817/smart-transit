"""Data access for Wallet + WalletTransaction. All wallet ORM lives here."""

from apps.common.repository import BaseRepository
from apps.payments.models import Wallet, WalletTransaction


class WalletRepository(BaseRepository):
    model = Wallet

    @classmethod
    def get_for_update(cls, user):
        """Row-locked wallet fetch — balance is mutated only under this lock so
        concurrent debits/credits serialize."""
        return Wallet.objects.select_for_update().filter(user=user).first()

    @classmethod
    def get_or_create(cls, user) -> Wallet:
        wallet, _ = Wallet.objects.get_or_create(user=user)
        return wallet

    @classmethod
    def get_for_user(cls, user):
        return Wallet.objects.filter(user=user).first()

    @classmethod
    def create_txn(cls, data: dict) -> WalletTransaction:
        return WalletTransaction.objects.create(**data)

    @classmethod
    def ledger(cls, wallet):
        # The (wallet, -created_at) index backs this list; cursor pager orders by created_at.
        return WalletTransaction.objects.filter(wallet=wallet)
