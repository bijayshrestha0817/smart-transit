from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self) -> None:
        # Register the drf-spectacular security scheme for CookieJWTAuthentication
        # (import side-effect populates the extension registry).
        from . import schema  # noqa: F401
