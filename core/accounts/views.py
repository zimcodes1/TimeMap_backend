from django.db import models
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdminOfficer, LecturerStaff, Student, User
from .permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_admin_officers,
    get_user_scope_departments,
)
from .serializers import (
    DEFAULT_NEW_USER_PASSWORD,
    AdminProfileSerializer,
    LecturerProfileSerializer,
    LoginSerializer,
    PasswordResetSerializer,
    StudentProfileSerializer,
    UserSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @extend_schema(
        request=LoginSerializer,
        summary="Authenticate User & Obtain Tokens",
        description="Authenticates a user via Matric Number or Staff ID and returns JWT tokens along with role and profile info.",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            user.last_login_at = timezone.now()
            user.save(update_fields=["last_login_at"])

            return Response(
                {
                    "user": UserSerializer(user).data,
                    "tokens": serializer.validated_data["tokens"],
                    "requires_password_reset": serializer.validated_data["requires_password_reset"],
                    "profile": serializer.validated_data["profile"],
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordResetSerializer

    @extend_schema(
        request=PasswordResetSerializer,
        summary="Forced First-Login Password Reset",
        description="Resets the password for the logged-in user and clears the requires_password_reset flag.",
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data["new_password"])
            user.requires_password_reset = False
            user.save(update_fields=["password", "requires_password_reset"])
            return Response(
                {"detail": "Password has been successfully updated. You may now access the application."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    @extend_schema(
        summary="Get Current User Profile",
        description="Retrieves identity and profile details for the currently authenticated user.",
    )
    def get(self, request):
        user = request.user
        profile_data = None
        if user.role == "student" and hasattr(user, "student_profile"):
            profile_data = StudentProfileSerializer(user.student_profile).data
        elif user.role == "lecturer" and hasattr(user, "lecturer_profile"):
            profile_data = LecturerProfileSerializer(user.lecturer_profile).data
        elif user.role == "admin" and hasattr(user, "admin_profile"):
            profile_data = AdminProfileSerializer(user.admin_profile).data

        return Response(
            {
                "user": UserSerializer(user).data,
                "profile": profile_data,
            }
        )


class BaseUserViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        instance = self.get_object()
        user = instance.user
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        instance = self.get_object()
        user = instance.user
        user.set_password(DEFAULT_NEW_USER_PASSWORD)
        user.requires_password_reset = True
        user.save(update_fields=["password", "requires_password_reset"])
        return Response({"detail": f"Password reset to default '{DEFAULT_NEW_USER_PASSWORD}' for {user.identifier}."})


class StudentViewSet(BaseUserViewSet):
    serializer_class = StudentProfileSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        dept_qs = get_user_scope_departments(self.request.user)
        return Student.objects.filter(department__in=dept_qs).exclude(user=self.request.user)


class LecturerViewSet(BaseUserViewSet):
    serializer_class = LecturerProfileSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        dept_qs = get_user_scope_departments(self.request.user)
        return LecturerStaff.objects.filter(department__in=dept_qs).exclude(user=self.request.user)


class AdminOfficerViewSet(BaseUserViewSet):
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, IsAdminUserRole]

    def get_queryset(self):
        return get_user_scope_admin_officers(self.request.user).exclude(user=self.request.user)
