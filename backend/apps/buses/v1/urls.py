"""Routes/stops + admin CRUD (v1), mounted at /api/v1/."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminBusViewSet,
    AdminDriverViewSet,
    AdminRouteViewSet,
    RouteDetailView,
    RouteListView,
    StopDetailView,
    StopListView,
)

app_name = "buses"

router = DefaultRouter()
router.register("admin/routes", AdminRouteViewSet, basename="admin-route")
router.register("admin/buses", AdminBusViewSet, basename="admin-bus")
router.register("admin/drivers", AdminDriverViewSet, basename="admin-driver")

urlpatterns = [
    path("routes/", RouteListView.as_view(), name="route-list"),
    path("routes/<int:pk>/", RouteDetailView.as_view(), name="route-detail"),
    path("stops/", StopListView.as_view(), name="stop-list"),
    path("stops/<int:pk>/", StopDetailView.as_view(), name="stop-detail"),
    *router.urls,
]
