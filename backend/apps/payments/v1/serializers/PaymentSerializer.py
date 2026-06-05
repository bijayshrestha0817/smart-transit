"""Payment serializers — checkout start + inbound webhook payload."""

from rest_framework import serializers

from apps.payments.enums import PaymentStatus


class CheckoutSerializer(serializers.Serializer):
    """Start a gateway checkout for an already-issued ticket."""

    ticket = serializers.IntegerField()


class CheckoutResponseSerializer(serializers.Serializer):
    """The adapter's checkout descriptor returned to the client."""

    txn_ref = serializers.CharField()
    gateway = serializers.CharField()
    status = serializers.CharField()
    checkout_ref = serializers.CharField(allow_null=True)


class WebhookSerializer(serializers.Serializer):
    """Inbound gateway webhook — idempotent confirmation keyed on ``txn_ref``."""

    txn_ref = serializers.CharField()
    status = serializers.ChoiceField(choices=PaymentStatus.choices)
    signature = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class WebhookResponseSerializer(serializers.Serializer):
    """The confirmed payment + ticket state echoed back to the gateway."""

    txn_ref = serializers.CharField()
    status = serializers.CharField()
    ticket_status = serializers.CharField()
    ticket = serializers.IntegerField()
