"""Ticket serializers — read (incl. QR + payment status), issue (write), refund."""

from rest_framework import serializers

from apps.payments.enums import PaymentGateway
from apps.payments.models import Ticket
from apps.trips.repository import TripRepository


class TicketSerializer(serializers.ModelSerializer):
    """Read representation of a ticket, including its QR token + payment status."""

    route_name = serializers.CharField(source="trip.route.name", read_only=True)
    payment_status = serializers.CharField(source="payment.status", read_only=True)
    gateway = serializers.CharField(source="payment.gateway", read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "passenger",
            "trip",
            "route_name",
            "qr_code",
            "status",
            "fare",
            "payment_status",
            "gateway",
            "created_at",
        )
        read_only_fields = fields


class IssueTicketSerializer(serializers.Serializer):
    """Issue payload — passenger picks a trip + gateway; price is server-side."""

    trip = serializers.IntegerField()
    gateway = serializers.ChoiceField(choices=PaymentGateway.choices)

    def validate_trip(self, value):
        trip = TripRepository.get_by_id(value)
        if trip is None:
            raise serializers.ValidationError("No active trip with this id.", code="invalid_trip")
        # Stash the loaded trip so the view doesn't re-query.
        self.context["trip_obj"] = trip
        return value


class RefundSerializer(serializers.Serializer):
    """Refund takes no body — present for schema/contract symmetry."""
