from django.contrib import admin

from .models import DriverLog


@admin.register(DriverLog)
class DriverLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "driver",
        "trip",
        "event_type",
        "timestamp",
        "is_deleted",
        "created_at",
    )
    list_filter = ("event_type", "is_deleted")
    search_fields = ("driver__email", "trip__id")
    ordering = ("-timestamp",)
    readonly_fields = ("created_at", "updated_at")
