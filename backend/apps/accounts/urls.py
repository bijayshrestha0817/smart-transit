"""Accounts app URL entry point — dispatches to versioned sub-APIs.

Mounted by config at /api/, so v1 auth endpoints resolve under /api/v1/auth/.
"""

from django.urls import include, path

urlpatterns = [
    path("v1/auth/", include("apps.accounts.v1.urls")),
    # path("v2/auth/", include("apps.accounts.v2.urls")),  # add when v2 lands
]
