"""Auth views. Tokens are delivered exclusively as HttpOnly cookies.

Views own the HTTP/cookie mechanics; AuthService owns the rules (credential checks,
verification, password reset). Cookie helpers stay here — they manipulate the Response,
which is a transport concern.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.v1.serializers import (
    EmailVerifySerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)
from apps.accounts.v1.services import AuthService
from apps.common.response import CustomResponse

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
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AuthService.register(serializer.validated_data)
        return CustomResponse(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=EmailVerifySerializer, responses={200: None})
    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.verify_email(serializer.context["uid"])
        return CustomResponse({"detail": "Email verified."})


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AuthService.login(
            request,
            serializer.validated_data["email"],
            serializer.validated_data["password"],
        )
        response = CustomResponse(UserSerializer(user).data)
        _issue_tokens(response, user)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
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
        response = CustomResponse({"detail": "Token refreshed."})
        _set_cookie(response, settings.JWT_AUTH_COOKIE, str(access), _ACCESS_MAX_AGE)
        _set_cookie(response, settings.JWT_AUTH_REFRESH_COOKIE, str(new_refresh), _REFRESH_MAX_AGE)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
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
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.request_password_reset(serializer.validated_data["email"])
        # Always the same response — never reveal whether the email exists.
        return CustomResponse({"detail": "If that account exists, a reset link has been sent."})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=ResetPasswordSerializer, responses={200: None})
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.reset_password(
            serializer.context["uid"], serializer.validated_data["new_password"]
        )
        return CustomResponse({"detail": "Password has been reset."})
