"""Auth-flow input serializers. Validation lives here; credential/state checks and
mutations live in AuthService."""

from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers

from apps.accounts import tokens
from apps.accounts.repository import AccountRepository

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "phone")

    def validate_email(self, value: str) -> str:
        value = value.lower()
        if AccountRepository.email_exists(value):
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    # Pure input shape — AuthService.login does the credential + verified checks.
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class EmailVerifySerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value: str) -> str:
        try:
            self.context["uid"] = tokens.read_email_verify_token(value)
        except tokens.SignatureExpired:
            raise serializers.ValidationError(
                "Verification link has expired.", code="token_expired"
            ) from None
        except tokens.BadSignature:
            raise serializers.ValidationError(
                "Invalid verification token.", code="token_invalid"
            ) from None
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_token(self, value: str) -> str:
        try:
            self.context["uid"] = tokens.read_password_reset_token(value)
        except tokens.SignatureExpired:
            raise serializers.ValidationError(
                "Reset link has expired.", code="token_expired"
            ) from None
        except tokens.BadSignature:
            raise serializers.ValidationError(
                "Invalid reset token.", code="token_invalid"
            ) from None
        return value

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value
