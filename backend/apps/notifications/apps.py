from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"

    def ready(self) -> None:
        # Connect the post_save signal that produces a TRIP_COMPLETED notification
        # off an existing domain event. Imported here (not at module load) so the
        # app registry is ready and the receivers register exactly once.
        from . import signals  # noqa: F401
