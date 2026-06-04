from django.contrib import admin

from .models import Payment, Ticket, Wallet, WalletTransaction


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "passenger",
        "trip",
        "status",
        "fare",
        "is_deleted",
        "created_at",
    )
    list_filter = ("status", "is_deleted")
    search_fields = ("passenger__email", "trip__id", "qr_code")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ticket",
        "amount",
        "gateway",
        "status",
        "txn_ref",
        "is_deleted",
        "created_at",
    )
    list_filter = ("gateway", "status", "is_deleted")
    search_fields = ("txn_ref", "ticket__id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "balance", "is_deleted", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("user__email",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "wallet",
        "kind",
        "amount",
        "balance_after",
        "reference",
        "created_at",
    )
    list_filter = ("kind", "is_deleted")
    search_fields = ("reference", "wallet__user__email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
