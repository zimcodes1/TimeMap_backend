from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProgramStudentCountViewSet

router = DefaultRouter()
router.register(r"programs", ProgramStudentCountViewSet, basename="student-count-programs")
router.register(r"departments", ProgramStudentCountViewSet, basename="student-count-departments")

urlpatterns = [path("", include(router.urls))]
