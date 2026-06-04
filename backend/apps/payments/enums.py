"""Enums for the payments app."""

from django.db import models


class TicketStatus(models.TextChoices):
    ISSUED = "issued", "Issued"
    ACTIVE = "active", "Active"
    USED = "used", "Used"
    EXPIRED = "expired", "Expired"
    REFUNDED = "refunded", "Refunded"
    CANCELLED = "cancelled", "Cancelled"


class PaymentGateway(models.TextChoices):
    KHALTI = "khalti", "Khalti"
    ESEWA = "esewa", "eSewa"
    STRIPE = "stripe", "Stripe"
    WALLET = "wallet", "Wallet"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class WalletTxnKind(models.TextChoices):
    CREDIT = "credit", "Credit"
    DEBIT = "debit", "Debit"
