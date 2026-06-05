"""Notification endpoints (v1), mounted at /api/v1/."""

from django.urls import path

from .views import NotificationFeedView, NotificationReadAllView, NotificationReadView

app_name = "notifications"

urlpatterns = [
    path("notifications/", NotificationFeedView.as_view(), name="notifications-feed"),
    path(
        "notifications/read-all/", NotificationReadAllView.as_view(), name="notifications-read-all"
    ),
    path("notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notifications-read"),
]
