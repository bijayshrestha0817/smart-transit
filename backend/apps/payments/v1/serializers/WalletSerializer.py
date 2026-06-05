"""Wallet serializers — balance summary + ledger row."""

from rest_framework import serializers

from apps.payments.models import WalletTransaction


class WalletSerializer(serializers.Serializer):
    """Wallet balance summary (`GET /wallet/`)."""

    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)


class WalletTransactionSerializer(serializers.ModelSerializer):
    """One append-only ledger row with its post-move balance snapshot."""

    class Meta:
        model = WalletTransaction
        fields = (
            "id",
            "kind",
            "amount",
            "balance_after",
            "reference",
            "payment",
            "created_at",
        )
        read_only_fields = fields
