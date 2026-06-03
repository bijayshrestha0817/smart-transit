"""Auth business logic. Views handle HTTP/cookies; this handles the rules."""

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.db import transaction

from apps.accounts import tokens
from apps.accounts.repository import AccountRepository
from apps.common.exceptions import CustomException


class AuthService:
    @staticmethod
    def register(data: dict):
        with transaction.atomic():
            user = AccountRepository.create_user(data)
        AuthService._send_verification_email(user)
        return user

    @staticmethod
    def verify_email(uid: int) -> None:
        user = AccountRepository.get_by_id(uid)
        if user and not user.is_verified:
            AccountRepository.mark_verified(user)

    @staticmethod
    def login(request, email: str, password: str):
        user = authenticate(request, username=email.lower(), password=password)
        if user is None:
            raise CustomException(
                message="Invalid email or password.", status=400, code="invalid_credentials"
            )
        if not user.is_verified:
            raise CustomException(
                message="Please verify your email before logging in.",
                status=400,
                code="not_verified",
            )
        return user

    @staticmethod
    def request_password_reset(email: str) -> None:
        # Always silent about whether the account exists.
        user = AccountRepository.get_active_by_email(email.lower())
        if user:
            token = tokens.make_password_reset_token(user.id)
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
            send_mail(
                subject="Reset your Smart Transit AI password",
                message=f"Reset your password: {reset_url}",
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )

    @staticmethod
    def reset_password(uid: int, new_password: str) -> None:
        user = AccountRepository.get_by_id(uid)
        if user:
            AccountRepository.set_password(user, new_password)

    @staticmethod
    def _send_verification_email(user) -> None:
        token = tokens.make_email_verify_token(user.id)
        verify_url = f"{settings.FRONTEND_URL}/verify?token={token}"
        send_mail(
            subject="Verify your Smart Transit AI account",
            message=f"Welcome! Confirm your email: {verify_url}",
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )
