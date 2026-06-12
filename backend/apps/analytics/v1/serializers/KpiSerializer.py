"""Output serializer for the admin KPI overview.

A plain ``serializers.Serializer`` (no model) — it types ``KpiService.overview()``'s flat
dict for the OpenAPI schema and renders ``revenue`` as a string (money-as-string contract).
Output only: no write path, no validation.
"""

from rest_framework import serializers


class KpiSerializer(serializers.Serializer):
    # Fleet (Bus.status composition + on-trip count)
    active_buses = serializers.IntegerField()  # distinct buses on an IN_PROGRESS trip
    total_buses = serializers.IntegerField()
    buses_active = serializers.IntegerField()
    buses_idle = serializers.IntegerField()
    buses_in_maintenance = serializers.IntegerField()
    buses_retired = serializers.IntegerField()

    # Trips — lifetime histogram
    scheduled_trips = serializers.IntegerField()
    active_trips = serializers.IntegerField()
    completed_trips = serializers.IntegerField()
    cancelled_trips = serializers.IntegerField()

    # Trips — today (keyed on created_at, the admin's local day)
    scheduled_trips_today = serializers.IntegerField()
    active_trips_today = serializers.IntegerField()
    completed_trips_today = serializers.IntegerField()
    cancelled_trips_today = serializers.IntegerField()

    # Ridership / money / operations (today)
    passengers_today = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)  # string, e.g. "35.00"
    avg_delay = serializers.FloatField(allow_null=True)  # minutes (1dp), null if no data
    open_alerts = serializers.IntegerField()
    maintenance_due = serializers.IntegerField()

    # Reference totals
    total_routes = serializers.IntegerField()
    total_drivers = serializers.IntegerField()
    verified_drivers = serializers.IntegerField()
