from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # OpenAPI Schema & Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API endpoints
    path("api/auth/", include("accounts.urls")),
    path("api/hierarchy/", include("hierarchy.urls")),
    path("api/venues/", include("venues.urls")),
    path("api/courses/", include("courses.urls")),
    path("api/scheduling/", include("scheduling.urls")),
    path("api/discrepancies/", include("discrepancies.urls")),
    path("api/reporting/", include("reporting.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/analytics/", include("analytics.urls")),
]
