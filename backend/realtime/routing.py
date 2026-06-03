"""WebSocket URL routing — consumed by ``config/asgi.py`` (api-contract §8)."""

from django.urls import re_path

from .consumers import (
    AlertsConsumer,
    DriverTripConsumer,
    FleetConsumer,
    NotificationsConsumer,
    TripConsumer,
)

websocket_urlpatterns = [
    re_path(r"^ws/driver/(?P<trip_id>\d+)/$", DriverTripConsumer.as_asgi()),
    re_path(r"^ws/trip/(?P<trip_id>\d+)/$", TripConsumer.as_asgi()),
    re_path(r"^ws/fleet/$", FleetConsumer.as_asgi()),
    re_path(r"^ws/alerts/$", AlertsConsumer.as_asgi()),
    re_path(r"^ws/notifications/$", NotificationsConsumer.as_asgi()),
]
