"""Data access for the User/account model. All account ORM lives here."""

from django.contrib.auth import get_user_model

from apps.common.repository import BaseRepository

User = get_user_model()


class AccountRepository(BaseRepository):
    model = User

    @classmethod
    def get_by_id(cls, user_id):
        # No is_deleted filter — matches the original verify/reset lookups.
        return User.objects.filter(id=user_id).first()

    @classmethod
    def get_active_by_email(cls, email: str):
        return User.objects.filter(email=email, is_active=True).first()

    @classmethod
    def email_exists(cls, email: str) -> bool:
        return User.objects.filter(email=email).exists()

    @classmethod
    def create_user(cls, data: dict):
        # New registrations are always passengers and start unverified.
        return User.objects.create_user(role=User.Roles.PASSENGER, **data)

    @classmethod
    def mark_verified(cls, user) -> None:
        user.is_verified = True
        user.save(update_fields=["is_verified", "updated_at"])

    @classmethod
    def set_password(cls, user, raw_password: str) -> None:
        user.set_password(raw_password)
        user.save(update_fields=["password", "updated_at"])
