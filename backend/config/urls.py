"""Root URL configuration.

Each app owns its own version dispatch (apps.<app>.urls → v1/, v2/, …) and is mounted
here under /api/, so the public surface stays /api/v1/… while versioning lives per app.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Per-app version dispatch (accounts owns /v1/auth/, buses owns /v1/{routes,stops,admin}/).
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.buses.urls")),
    # OpenAPI schema + Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
