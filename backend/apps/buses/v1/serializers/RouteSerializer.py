"""Route serializers — list, detail (with stops), write."""

from rest_framework import serializers

from apps.buses.models import Route

from .BusStopSerializer import BusStopSerializer


class RouteListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("id", "name", "color", "estimated_duration", "created_at")
        read_only_fields = fields


class RouteDetailSerializer(serializers.ModelSerializer):
    stops = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = (
            "id",
            "name",
            "color",
            "estimated_duration",
            "polyline_json",
            "created_at",
            "stops",
        )
        read_only_fields = fields

    def get_stops(self, obj: Route) -> list[dict]:
        # ``ordered_stops`` is prefetched (in sequence order) by
        # RouteRepository.get_with_stops — no ORM in the serializer.
        stops = getattr(obj, "ordered_stops", [])
        return BusStopSerializer(stops, many=True).data


class RouteWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("name", "color", "estimated_duration", "polyline_json")
