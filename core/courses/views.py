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
from .permissions import CanManageCourse, CanManageCourseGrant
from .serializers import (
    CourseAccessGrantSerializer,
    CourseRegistrationSerializer,
    CourseSerializer,
)
from .services import get_visible_courses_for_student


class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageCourse]

    def get_queryset(self):
        user = self.request.user
        if user.role == "student" and hasattr(user, "student_profile"):
            return get_visible_courses_for_student(user.student_profile)

        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return Course.objects.all()

        if user.role == "admin" and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            level = admin_prof.level

            if level in ["university", "school"]:
                # System level & School level can view all courses
                return Course.objects.all()

            elif level == "faculty":
                if not admin_prof.scope_faculty:
                    return Course.objects.none()

                # Get IDs of courses granted to or requested by this faculty / departments in this faculty
                granted_course_ids = CourseAccessGrant.objects.filter(
                    Q(granted_to_faculty=admin_prof.scope_faculty)
                    | Q(granted_to_department__faculty=admin_prof.scope_faculty)
                    | Q(course__owning_faculty=admin_prof.scope_faculty)
                    | Q(course__owning_department__faculty=admin_prof.scope_faculty)
                ).values_list("course_id", flat=True)

                return Course.objects.filter(
                    Q(owning_level=Course.OwningLevel.FACULTY, owning_faculty=admin_prof.scope_faculty)
                    | Q(owning_level=Course.OwningLevel.DEPARTMENT, owning_department__faculty=admin_prof.scope_faculty)
                    | Q(id__in=granted_course_ids)
                ).distinct()

            elif level == "department":
                if not admin_prof.scope_department:
                    return Course.objects.none()

                granted_course_ids = CourseAccessGrant.objects.filter(
                    Q(granted_to_department=admin_prof.scope_department)
                    | Q(course__owning_department=admin_prof.scope_department)
                ).values_list("course_id", flat=True)

                return Course.objects.filter(
                    Q(owning_level=Course.OwningLevel.DEPARTMENT, owning_department=admin_prof.scope_department)
                    | Q(id__in=granted_course_ids)
                ).distinct()

        return Course.objects.none()

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
    permission_classes = [IsAuthenticated, IsPasswordResetDone, IsAdminUserRole, CanManageCourseGrant]

    def get_queryset(self):
        user = self.request.user
        dept_qs = get_user_scope_departments(user)
        fac_qs = get_user_scope_faculties(user)

        # Access grants related to course owner side or granted recipient side
        return CourseAccessGrant.objects.filter(
            Q(course__owning_department__in=dept_qs)
            | Q(course__owning_faculty__in=fac_qs)
            | Q(granted_to_department__in=dept_qs)
            | Q(granted_to_faculty__in=fac_qs)
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
