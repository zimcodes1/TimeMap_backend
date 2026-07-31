from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CourseAccessGrantViewSet, CourseRegistrationViewSet, CourseViewSet

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"grants", CourseAccessGrantViewSet, basename="course-access-grant")
router.register(r"registrations", CourseRegistrationViewSet, basename="course-registration")

urlpatterns = [
    path("", include(router.urls)),
]
