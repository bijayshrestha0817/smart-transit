from django.contrib import admin

from .models import GpsLocation, Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bus",
        "route",
        "driver",
        "status",
        "start_time",
        "is_deleted",
        "created_at",
    )
    list_filter = ("status", "is_deleted")
    search_fields = ("bus__plate", "route__name", "driver__email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(GpsLocation)
class GpsLocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trip",
        "lat",
        "lng",
        "speed",
        "heading",
        "timestamp",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_deleted",)
    search_fields = ("trip__id",)
    ordering = ("-timestamp",)
    readonly_fields = ("created_at", "updated_at")
