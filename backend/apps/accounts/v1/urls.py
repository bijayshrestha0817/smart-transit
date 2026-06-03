"""Auth routes (v1), mounted under /api/v1/auth/."""

from django.urls import path

from .views import (
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    RegisterView,
    ResetPasswordView,
    VerifyEmailView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("me/", MeView.as_view(), name="me"),
]
