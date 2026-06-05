"""Maintenance log admin CRUD (v1), mounted at /api/v1/."""

from rest_framework.routers import DefaultRouter

from .views import AdminMaintenanceLogViewSet

app_name = "maintenance"

router = DefaultRouter()
router.register(
    "admin/maintenance-logs", AdminMaintenanceLogViewSet, basename="admin-maintenance-log"
)

urlpatterns = [*router.urls]
