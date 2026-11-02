from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
)
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Course, CourseAccessGrant, CourseRegistration
from .permissions import CanManageCourse, CanManageCourseGrant
from .serializers import (
    CourseAccessGrantSerializer,
    CourseRegistrationSerializer,
    CourseSerializer,
)
from .services import (
    annotate_courses_with_student_counts,
    get_visible_courses_for_student,
)


class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageCourse]

    def get_queryset(self):
        user = self.request.user
        base_qs = None

        if user.role == "student" and hasattr(user, "student_profile"):
            base_qs = get_visible_courses_for_student(user.student_profile)

        elif user.role == "lecturer" and hasattr(user, "lecturer_profile"):
            base_qs = Course.objects.filter(lecturers=user.lecturer_profile)

        elif user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            base_qs = Course.objects.all()

        elif (user.role in ["admin", "system_admin"] or user.is_superuser) and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            level = admin_prof.level

            if level in ["system", "university", "school"]:
                # System level & School level can view all courses
                base_qs = Course.objects.all()

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

                base_qs = Course.objects.filter(
                    Q(owning_level=Course.OwningLevel.FACULTY, owning_faculty=admin_prof.scope_faculty)
                    | Q(owning_level=Course.OwningLevel.DEPARTMENT, owning_department__faculty=admin_prof.scope_faculty)
                    | Q(id__in=granted_course_ids)
                    | (Q(owning_level=Course.OwningLevel.SCHOOL, owning_school=admin_prof.scope_faculty.school) if admin_prof.scope_faculty.school else Q())
                    | Q(owning_level=Course.OwningLevel.GENERAL)
                    | Q(lecturers__department__faculty=admin_prof.scope_faculty)
                ).distinct()

            elif level == "department":
                if not admin_prof.scope_department:
                    return Course.objects.none()

                dept = admin_prof.scope_department
                fac = dept.faculty
                sch = fac.school if fac else None

                granted_course_ids = CourseAccessGrant.objects.filter(
                    status=CourseAccessGrant.Status.APPROVED,
                    granted_to_department=dept,
                ).values_list("course_id", flat=True)

                base_qs = Course.objects.filter(
                    Q(owning_level=Course.OwningLevel.DEPARTMENT, owning_department=dept)
                    | Q(id__in=granted_course_ids)
                    | (Q(owning_level=Course.OwningLevel.FACULTY, owning_faculty=fac) if fac else Q())
                    | (Q(owning_level=Course.OwningLevel.SCHOOL, owning_school=sch) if sch else Q())
                    | Q(owning_level=Course.OwningLevel.GENERAL)
                    | Q(lecturers__department=dept)
                ).distinct()

        if base_qs is None:
            return Course.objects.none()

        semester_param = self.request.query_params.get("semester")
        if semester_param:
            base_qs = base_qs.filter(semester_id=semester_param)
        program_param = self.request.query_params.get("program")
        if program_param:
            base_qs = base_qs.filter(
                Q(target_program_id=program_param)
                | Q(program_scope="general")
            )
        lecturer_param = self.request.query_params.get("lecturer")
        if lecturer_param:
            if str(lecturer_param).isdigit():
                base_qs = base_qs.filter(
                    Q(lecturers__id=int(lecturer_param))
                    | Q(lecturers__user_id=int(lecturer_param))
                    | Q(lecturers__staff_id=str(lecturer_param))
                ).distinct()
            else:
                base_qs = base_qs.filter(
                    Q(lecturers__staff_id=str(lecturer_param))
                    | Q(lecturers__user__identifier=str(lecturer_param))
                ).distinct()

        return base_qs.select_related(
            "owning_department",
            "owning_faculty",
            "owning_school",
            "target_program",
            "semester",
            "semester__session",
        ).prefetch_related(
            "lecturers",
            "access_grants",
            "access_grants__target_program",
            "access_grants__granted_to_department",
            "access_grants__granted_to_faculty",
            "access_grants__granted_to_school",
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            annotate_courses_with_student_counts(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        courses = list(queryset)
        annotate_courses_with_student_counts(courses)
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)

    @extend_schema(summary="Get courses visible to authenticated student", responses={200: CourseSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="visible-to-me")
    def visible_to_me(self, request):
        if hasattr(request.user, "student_profile"):
            qs = get_visible_courses_for_student(request.user.student_profile)
            courses = list(qs)
            annotate_courses_with_student_counts(courses)
            serializer = self.get_serializer(courses, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({"detail": "Only students have a visible course list."}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Get current user exam configuration access status")
    @action(detail=False, methods=["get"], url_path="exam-settings-access")
    def exam_settings_access(self, request):
        from accounts.models import AdminOfficer

        user = request.user
        admin_prof = getattr(user, "admin_profile", None)
        if not admin_prof:
            return Response({
                "is_exam_officer": False,
                "has_scope_exam_officer": False,
                "can_access_exam_tab": False,
            })

        is_eo = getattr(admin_prof, "is_exam_officer", False)
        has_officer = False
        if is_eo:
            has_officer = True
        elif admin_prof.level == "department" and admin_prof.scope_department_id:
            has_officer = AdminOfficer.objects.filter(
                is_exam_officer=True, user__is_active=True, scope_department_id=admin_prof.scope_department_id
            ).exists()
        elif admin_prof.level == "faculty" and admin_prof.scope_faculty_id:
            has_officer = AdminOfficer.objects.filter(
                is_exam_officer=True, user__is_active=True, scope_faculty_id=admin_prof.scope_faculty_id
            ).exists()
        elif admin_prof.level == "school" and admin_prof.scope_school_id:
            has_officer = AdminOfficer.objects.filter(
                is_exam_officer=True, user__is_active=True, scope_school_id=admin_prof.scope_school_id
            ).exists()

        can_access_exam_tab = is_eo or (not has_officer)
        return Response({
            "is_exam_officer": is_eo,
            "has_scope_exam_officer": has_officer,
            "can_access_exam_tab": can_access_exam_tab,
        })


class CourseAccessGrantViewSet(viewsets.ModelViewSet):
    serializer_class = CourseAccessGrantSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, IsAdminUserRole, CanManageCourseGrant]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return CourseAccessGrant.objects.all()
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

    def _user_can_undo_grant(self, user, grant):
        """
        Only the admin to which access was granted (the grantee / recipient side)
        is authorized to undo this access grant.
        """
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True

        admin_prof = getattr(user, "admin_profile", None)
        if not admin_prof:
            return False

        dept_qs = get_user_scope_departments(user)
        fac_qs = get_user_scope_faculties(user)

        # Must be on the recipient side (the scope to which access was granted)
        is_recipient = (
            (grant.granted_to_department_id and grant.granted_to_department in dept_qs)
            or (grant.granted_to_faculty_id and grant.granted_to_faculty in fac_qs)
            or (grant.granted_to_school_id and admin_prof.scope_school_id == grant.granted_to_school_id)
        )

        return bool(is_recipient)

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

    @extend_schema(summary="Undo course access grant", responses={200: dict})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        grant = self.get_object()
        if not self._user_can_undo_grant(request.user, grant):
            raise PermissionDenied("Only the admin to which access was granted can undo this grant.")

        course = grant.course
        course_code = course.code
        grant_id = grant.id

        recipient_dept = grant.granted_to_department
        recipient_fac = grant.granted_to_faculty

        # Clean up any timetable entries or lecture sessions created by or targeted to the recipient scope
        from scheduling.models import LectureSession, TimetableEntry

        entry_cleanup_q = Q(course=course)
        if recipient_dept:
            entry_cleanup_q &= (
                Q(created_by__scope_department=recipient_dept)
                | Q(target_program__department=recipient_dept)
            )
        elif recipient_fac:
            entry_cleanup_q &= (
                Q(created_by__scope_faculty=recipient_fac)
                | Q(target_program__department__faculty=recipient_fac)
            )

        entries_to_remove = TimetableEntry.objects.filter(entry_cleanup_q)
        if entries_to_remove.exists():
            LectureSession.objects.filter(timetable_entry__in=entries_to_remove).delete()
            entries_to_remove.delete()

        grant.delete()
        return Response(
            {"detail": f"Access grant for {course_code} undone successfully.", "id": grant_id},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        grant = self.get_object()
        if grant.status == CourseAccessGrant.Status.APPROVED:
            if not self._user_can_undo_grant(request.user, grant):
                raise PermissionDenied("Only the admin to which access was granted can undo this grant.")
        return super().destroy(request, *args, **kwargs)


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
