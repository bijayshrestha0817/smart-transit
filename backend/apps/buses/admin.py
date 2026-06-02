from django.contrib import admin

from .models import Bus, BusStop, Route


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "estimated_duration", "is_deleted", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    list_display = ("name", "route", "sequence", "lat", "lng", "is_deleted", "created_at")
    list_filter = ("route", "is_deleted")
    search_fields = ("name",)
    ordering = ("route", "sequence")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ("plate", "capacity", "status", "assigned_driver", "is_deleted", "created_at")
    list_filter = ("status", "is_deleted")
    search_fields = ("plate",)
    ordering = ("plate",)
    readonly_fields = ("created_at", "updated_at")
