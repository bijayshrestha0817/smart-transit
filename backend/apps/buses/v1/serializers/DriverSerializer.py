"""Driver serializers (accounts.User rows with role=driver)."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.buses.repository import DriverRepository

User = get_user_model()


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone", "is_verified", "created_at")
        read_only_fields = fields


class DriverWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "password", "full_name", "phone")

    def validate_email(self, value: str) -> str:
        value = value.lower()
        exclude_pk = self.instance.pk if self.instance is not None else None
        if DriverRepository.email_exists(value, exclude_pk=exclude_pk):
            raise serializers.ValidationError(
                "A user with this email already exists.", code="duplicate_email"
            )
        return value
