"""User representation serializer (no secrets)."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user."""

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone", "role", "is_verified", "created_at")
        read_only_fields = fields
