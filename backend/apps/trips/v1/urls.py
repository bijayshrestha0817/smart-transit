"""Trip endpoints (v1), mounted at /api/v1/.

DefaultRouter handles the ViewSets (admin CRUD + the driver lifecycle actions);
plain ``path()`` handles the single-purpose APIViews.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ActiveTripsView,
    AdminTripViewSet,
    DriverTripViewSet,
    FleetSnapshotView,
    TripEtaView,
)

app_name = "trips"

router = DefaultRouter()
router.register("admin/trips", AdminTripViewSet, basename="admin-trip")
router.register("driver/trips", DriverTripViewSet, basename="driver-trip")

urlpatterns = [
    path("trips/active/", ActiveTripsView.as_view(), name="trips-active"),
    path("trips/<int:pk>/eta/", TripEtaView.as_view(), name="trips-eta"),
    path("admin/fleet/", FleetSnapshotView.as_view(), name="admin-fleet"),
    *router.urls,
]
