from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Course, CourseAccessGrant, CourseRegistration
from .serializers import (
    CourseAccessGrantSerializer,
    CourseRegistrationSerializer,
    CourseSerializer,
)
from .services import get_visible_courses_for_student


class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        if user.role == "student" and hasattr(user, "student_profile"):
            return get_visible_courses_for_student(user.student_profile)

        dept_qs = get_user_scope_departments(user)
        fac_qs = get_user_scope_faculties(user)
        sch_qs = get_user_scope_schools(user)

        scope_filter = (
            Q(owning_level=Course.OwningLevel.GENERAL)
            | Q(owning_level=Course.OwningLevel.DEPARTMENT, owning_department__in=dept_qs)
            | Q(owning_level=Course.OwningLevel.FACULTY, owning_faculty__in=fac_qs)
            | Q(owning_level=Course.OwningLevel.SCHOOL, owning_school__in=sch_qs)
        )
        return Course.objects.filter(scope_filter).distinct()

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPasswordResetDone(), IsAdminUserRole()]
        return super().get_permissions()

    @extend_schema(summary="Get courses visible to authenticated student", responses={200: CourseSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="visible-to-me")
    def visible_to_me(self, request):
        if hasattr(request.user, "student_profile"):
            qs = get_visible_courses_for_student(request.user.student_profile)
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({"detail": "Only students have a visible course list."}, status=status.HTTP_400_BAD_REQUEST)


class CourseAccessGrantViewSet(viewsets.ModelViewSet):
    serializer_class = CourseAccessGrantSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, IsAdminUserRole]

    def get_queryset(self):
        user = self.request.user
        dept_qs = get_user_scope_departments(user)
        fac_qs = get_user_scope_faculties(user)
        sch_qs = get_user_scope_schools(user)

        # Access grants related to course owner side or granted recipient side
        return CourseAccessGrant.objects.filter(
            Q(course__owning_department__in=dept_qs)
            | Q(course__owning_faculty__in=fac_qs)
            | Q(course__owning_school__in=sch_qs)
            | Q(granted_to_department__in=dept_qs)
            | Q(granted_to_faculty__in=fac_qs)
            | Q(granted_to_school__in=sch_qs)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(initiated_by=self.request.user.admin_profile)

    @extend_schema(summary="Approve course access grant", responses={200: CourseAccessGrantSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        grant = self.get_object()
        grant.status = CourseAccessGrant.Status.APPROVED
        grant.decided_by = request.user.admin_profile
        grant.decided_at = timezone.now()
        grant.save(update_fields=["status", "decided_by", "decided_at"])
        return Response(CourseAccessGrantSerializer(grant).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Reject course access grant", responses={200: CourseAccessGrantSerializer})
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        grant = self.get_object()
        grant.status = CourseAccessGrant.Status.REJECTED
        grant.decided_by = request.user.admin_profile
        grant.decided_at = timezone.now()
        grant.save(update_fields=["status", "decided_by", "decided_at"])
        return Response(CourseAccessGrantSerializer(grant).data, status=status.HTTP_200_OK)


class CourseRegistrationViewSet(viewsets.ModelViewSet):
    serializer_class = CourseRegistrationSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        if user.role == "student" and hasattr(user, "student_profile"):
            return CourseRegistration.objects.filter(student=user.student_profile)

        dept_qs = get_user_scope_departments(user)
        return CourseRegistration.objects.filter(student__department__in=dept_qs)

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == "student" and hasattr(user, "student_profile"):
            serializer.save(student=user.student_profile)
        else:
            serializer.save()
