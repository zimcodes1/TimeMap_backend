from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminOfficerViewSet,
    LecturerViewSet,
    LoginView,
    PasswordResetView,
    StudentViewSet,
    UserProfileView,
)

router = DefaultRouter()
router.register(r"students", StudentViewSet, basename="student")
router.register(r"lecturers", LecturerViewSet, basename="lecturer")
router.register(r"admins", AdminOfficerViewSet, basename="admin-officer")

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth_login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth_token_refresh"),
    path("password-reset/", PasswordResetView.as_view(), name="auth_password_reset"),
    path("profile/", UserProfileView.as_view(), name="user_profile"),
    path("", include(router.urls)),
]
