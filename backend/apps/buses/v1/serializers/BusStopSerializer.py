"""Stop serializers — read representation + assign-stops payload."""

from rest_framework import serializers

from apps.buses.models import BusStop


class BusStopSerializer(serializers.ModelSerializer):
    """Read representation of a stop."""

    class Meta:
        model = BusStop
        fields = ("id", "name", "lat", "lng", "route", "sequence", "created_at")
        read_only_fields = fields


class _StopEntrySerializer(serializers.Serializer):
    """One stop in an assign-stops payload — ``route`` comes from the URL."""

    name = serializers.CharField(max_length=120)
    lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    sequence = serializers.IntegerField(min_value=0)


class AssignStopsSerializer(serializers.Serializer):
    """A list of stops that replaces the route's existing stops."""

    stops = _StopEntrySerializer(many=True)
