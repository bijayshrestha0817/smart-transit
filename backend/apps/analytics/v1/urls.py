"""Analytics endpoints (v1), mounted at /api/v1/.

A single admin KPI/overview endpoint for now. The Recharts/time-series analytics
endpoints (backed by ``analytics_snapshots`` + Celery rollups) land in a later P6 slice.
"""

from django.urls import path

from .views import KpiOverviewView

app_name = "analytics"

urlpatterns = [
    path("admin/overview/kpis/", KpiOverviewView.as_view(), name="admin-overview-kpis"),
]
