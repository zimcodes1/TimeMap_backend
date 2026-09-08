from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DepartmentStudentCountViewSet

router = DefaultRouter()
router.register(r"departments", DepartmentStudentCountViewSet, basename="student-count")

urlpatterns = [path("", include(router.urls))]
