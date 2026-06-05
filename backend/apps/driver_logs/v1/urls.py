"""Driver log endpoints (v1), mounted at /api/v1/."""

from django.urls import path

from .views import DriverLogCreateView, DriverSosView

app_name = "driver_logs"

urlpatterns = [
    path("driver/logs/", DriverLogCreateView.as_view(), name="driver-logs-create"),
    path("driver/sos/", DriverSosView.as_view(), name="driver-sos"),
]
