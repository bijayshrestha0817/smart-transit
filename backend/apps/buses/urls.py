"""Buses app URL entry point — dispatches to versioned sub-APIs.

Mounted by config at /api/, so v1 endpoints resolve under /api/v1/.
"""

from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.buses.v1.urls")),
    # path("v2/", include("apps.buses.v2.urls")),  # add when v2 lands
]
