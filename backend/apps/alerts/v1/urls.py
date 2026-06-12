"""Alert endpoints (v1), mounted at /api/v1/."""

from django.urls import path

from .views import AlertAcknowledgeView, AlertFeedView

app_name = "alerts"

urlpatterns = [
    path("admin/alerts/", AlertFeedView.as_view(), name="admin-alerts"),
    path(
        "admin/alerts/<int:pk>/acknowledge/",
        AlertAcknowledgeView.as_view(),
        name="admin-alerts-acknowledge",
    ),
]
