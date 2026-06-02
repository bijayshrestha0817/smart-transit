from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "is_verified", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_verified", "is_active", "is_staff", "is_deleted")
    search_fields = ("email", "full_name", "phone")
    ordering = ("email",)
    readonly_fields = ("created_at", "updated_at", "last_login")
    # Passwords are set via the API / `createsuperuser`, not the raw hash field.
    exclude = ("password", "groups", "user_permissions")
