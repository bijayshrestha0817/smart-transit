"""Enums for the accounts app."""

from django.db import models


class UserRole(models.TextChoices):
    PASSENGER = "passenger", "Passenger"
    DRIVER = "driver", "Driver"
    ADMIN = "admin", "Admin"
