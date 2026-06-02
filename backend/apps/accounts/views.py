"""Auth views. Tokens are delivered exclusively as HttpOnly cookies."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from . import tokens
from .serializers import (
    EmailVerifySerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)

User = get_user_model()

_ACCESS_MAX_AGE = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
_REFRESH_MAX_AGE = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=settings.JWT_AUTH_COOKIE_HTTPONLY,
        secure=settings.JWT_AUTH_COOKIE_SECURE,
        samesite=settings.JWT_AUTH_COOKIE_SAMESITE,
        path=settings.JWT_AUTH_COOKIE_PATH,
    )


def _issue_tokens(response: Response, user) -> None:
    """Mint an access+refresh pair (with the role claim) and set both cookies."""
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    access = refresh.access_token
    access["role"] = user.role
    _set_cookie(response, settings.JWT_AUTH_COOKIE, str(access), _ACCESS_MAX_AGE)
    _set_cookie(response, settings.JWT_AUTH_REFRESH_COOKIE, str(refresh), _REFRESH_MAX_AGE)


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(settings.JWT_AUTH_COOKIE, path=settings.JWT_AUTH_COOKIE_PATH)
    response.delete_cookie(settings.JWT_AUTH_REFRESH_COOKIE, path=settings.JWT_AUTH_COOKIE_PATH)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token = tokens.make_email_verify_token(user.id)
        verify_url = f"{settings.FRONTEND_URL}/verify?token={token}"
        send_mail(
            subject="Verify your Smart Transit AI account",
            message=f"Welcome! Confirm your email: {verify_url}",
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=EmailVerifySerializer, responses={200: None})
    def post(self, request: Request) -> Response:
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(id=serializer.context["uid"]).first()
        if user and not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified", "updated_at"])
        return Response({"detail": "Email verified."})


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        response = Response(UserSerializer(user).data)
        _issue_tokens(response, user)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: None})
    def post(self, request: Request) -> Response:
        raw = request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE)
        if not raw:
            raise NotAuthenticated("No refresh token cookie present.")

        serializer = TokenRefreshSerializer(data={"refresh": raw})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken("Refresh token is invalid or expired.") from exc

        access = serializer.validated_data["access"]
        # ROTATE_REFRESH_TOKENS=True returns a fresh refresh and blacklists the old.
        new_refresh = serializer.validated_data.get("refresh", raw)
        response = Response({"detail": "Token refreshed."})
        _set_cookie(response, settings.JWT_AUTH_COOKIE, str(access), _ACCESS_MAX_AGE)
        _set_cookie(response, settings.JWT_AUTH_REFRESH_COOKIE, str(new_refresh), _REFRESH_MAX_AGE)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        raw = request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass  # already invalid/expired — nothing to revoke
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_cookies(response)
        return response


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=ForgotPasswordSerializer, responses={200: None})
    def post(self, request: Request) -> Response:
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        user = User.objects.filter(email=email, is_active=True).first()
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
        # Always the same response — never reveal whether the email exists.
        return Response({"detail": "If that account exists, a reset link has been sent."})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=ResetPasswordSerializer, responses={200: None})
    def post(self, request: Request) -> Response:
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(id=serializer.context["uid"]).first()
        if user:
            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password", "updated_at"])
        return Response({"detail": "Password has been reset."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)
