"""Serializers for auth flows. Validation lives here; views stay thin."""

from django.contrib.auth import authenticate, get_user_model, password_validation
from rest_framework import serializers

from . import tokens

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user (no secrets)."""

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone", "role", "is_verified", "created_at")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "phone")

    def validate_email(self, value: str) -> str:
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        # New registrations are always passengers and start unverified.
        return User.objects.create_user(role=User.Roles.PASSENGER, **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            self.context.get("request"),
            username=attrs["email"].lower(),
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError(
                "Invalid email or password.", code="invalid_credentials"
            )
        if not user.is_verified:
            raise serializers.ValidationError(
                "Please verify your email before logging in.", code="not_verified"
            )
        attrs["user"] = user
        return attrs


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
