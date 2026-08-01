from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ClassRepReportViewSet, UnreportedSessionFlagViewSet

router = DefaultRouter()
router.register("reports", ClassRepReportViewSet, basename="class-rep-report")
router.register("flags", UnreportedSessionFlagViewSet, basename="unreported-flag")

urlpatterns = [
    path("", include(router.urls)),
]
