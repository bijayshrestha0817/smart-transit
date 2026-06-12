"""Alerts app URL entry point — dispatches to versioned sub-APIs.

Mounted by config at /api/, so v1 endpoints resolve under /api/v1/.
"""

from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.alerts.v1.urls")),
]
