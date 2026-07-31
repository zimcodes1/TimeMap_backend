from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FacilityViewSet, VenueViewSet

router = DefaultRouter()
router.register(r"facilities", FacilityViewSet, basename="facility")
router.register(r"venues", VenueViewSet, basename="venue")

urlpatterns = [
    path("", include(router.urls)),
]
