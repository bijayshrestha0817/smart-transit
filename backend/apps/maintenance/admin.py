from django.contrib import admin

from .models import MaintenanceLog


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bus",
        "service_type",
        "cost",
        "serviced_at",
        "next_due",
        "is_deleted",
        "created_at",
    )
    list_filter = ("bus", "is_deleted")
    search_fields = ("service_type", "bus__plate")
    ordering = ("-serviced_at",)
    readonly_fields = ("created_at", "updated_at")
