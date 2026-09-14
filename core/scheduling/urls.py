from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcademicSessionViewSet,
    ExamSittingViewSet,
    LectureSessionViewSet,
    SemesterViewSet,
    TimetableEntryViewSet,
    TimetableGenerationViewSet,
)

router = DefaultRouter()
router.register(r"academic-sessions", AcademicSessionViewSet, basename="academic-session")
router.register(r"semesters", SemesterViewSet, basename="semester")
router.register(r"entries", TimetableEntryViewSet, basename="timetable-entry")
router.register(r"sessions", LectureSessionViewSet, basename="lecture-session")
router.register(r"exam-sittings", ExamSittingViewSet, basename="exam-sitting")
router.register(r"generate", TimetableGenerationViewSet, basename="timetable-generate")

urlpatterns = [
    path("", include(router.urls)),
]
