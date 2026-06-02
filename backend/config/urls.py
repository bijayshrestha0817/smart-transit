"""Root URL configuration. API is versioned under /api/v1/."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# /api/v1/* — versioned API surface. New apps add their routers here as they land.
api_v1_patterns = [
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.buses.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "v1"))),
    # OpenAPI schema + Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
