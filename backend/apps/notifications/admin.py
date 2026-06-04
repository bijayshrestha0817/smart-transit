from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "type",
        "read_at",
        "is_deleted",
        "created_at",
    )
    list_filter = ("type", "is_deleted")
    search_fields = ("user__email",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
