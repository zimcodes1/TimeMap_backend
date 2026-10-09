from datetime import date
from typing import Any, Dict, Optional
from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import datetime
from .models import (
    AcademicSession,
    ExamSitting,
    FacultyExamPeriod,
    GenerationScopePermission,
    LectureSession,
    Semester,
    TimetableEntry,
    TimetableGenerationRun,
)
from .optimizer.generator import generate_timetable
from .optimizer.genetic.algorithm import OptimizerConfig
from .optimizer.preprocessing.export import (
    serialize_problem_to_csv,
    serialize_problem_to_dict,
)
from .optimizer.preprocessing.pipeline import build_scheduling_problem_from_db
from .optimizer.publisher import publish_generation_run
from .permissions import (
    CanGenerateTimetable,
    CanManageSessionAndSemester,
    check_scope_generation_permission,
)
from .serializers import (
    AcademicSessionSerializer,
    ExamSittingSerializer,
    FacultyExamPeriodSerializer,
    GenerateTimetableRequestSerializer,
    GenerationScopePermissionSerializer,
    LectureSessionSerializer,
    SemesterSerializer,
    TimetableEntrySerializer,
    TimetableGenerationRunDetailSerializer,
    TimetableGenerationRunSerializer,
)
from .services import get_effective_exam_period, materialize_timetable_entry


class AcademicSessionViewSet(viewsets.ModelViewSet):
    serializer_class = AcademicSessionSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageSessionAndSemester]

    def get_queryset(self):
        user = self.request.user
        qs = AcademicSession.objects.select_related("school").prefetch_related("semesters")
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            pass
        else:
            qs = qs.filter(school__in=get_user_scope_schools(user))

        school_id = self.request.query_params.get("school")
        if school_id:
            qs = qs.filter(school_id=school_id)
        is_current = self.request.query_params.get("is_current")
        if is_current is not None:
            qs = qs.filter(is_current=is_current.lower() in ["true", "1"])
        return qs.order_by("-start_date")

    def perform_create(self, serializer):
        is_current = serializer.validated_data.get("is_current", False)
        school = serializer.validated_data.get("school")
        if is_current and school:
            AcademicSession.objects.filter(school=school).update(is_current=False)
        serializer.save()

    def perform_update(self, serializer):
        is_current = serializer.validated_data.get("is_current", False)
        instance = serializer.instance
        school = serializer.validated_data.get("school", instance.school)
        if is_current and school:
            AcademicSession.objects.filter(school=school).exclude(id=instance.id).update(is_current=False)
        serializer.save()

    @extend_schema(summary="Set this session as current for the school", responses={200: AcademicSessionSerializer})
    @action(detail=True, methods=["post"], url_path="set-current")
    def set_current(self, request, pk=None):
        session = self.get_object()
        AcademicSession.objects.filter(school=session.school).exclude(id=session.id).update(is_current=False)
        session.is_current = True
        session.save(update_fields=["is_current"])
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)


class SemesterViewSet(viewsets.ModelViewSet):
    serializer_class = SemesterSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageSessionAndSemester]

    def get_queryset(self):
        user = self.request.user
        qs = Semester.objects.select_related("session__school", "created_by")
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            pass
        else:
            qs = qs.filter(session__school__in=get_user_scope_schools(user))

        session_id = self.request.query_params.get("session")
        if session_id:
            qs = qs.filter(session_id=session_id)
        school_id = self.request.query_params.get("school")
        if school_id:
            qs = qs.filter(session__school_id=school_id)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ["true", "1"])
        return qs.order_by("-start_date")

    def perform_create(self, serializer):
        admin_prof = getattr(self.request.user, "admin_profile", None)
        serializer.save(created_by=admin_prof)

    def get_permissions(self):
        if self.action in ["faculty_exam_periods", "effective_exam_period"]:
            return [IsAuthenticated(), IsPasswordResetDone()]
        return super().get_permissions()

    @extend_schema(summary="Activate this semester for the school", responses={200: SemesterSerializer})
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        semester = self.get_object()
        school = semester.session.school
        # Deactivate any other semesters for this school
        Semester.objects.filter(session__school=school).exclude(id=semester.id).update(is_active=False)
        semester.is_active = True
        semester.save(update_fields=["is_active"])
        return Response(SemesterSerializer(semester).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Set or update school-wide exam period for a semester", responses={200: SemesterSerializer})
    @action(detail=True, methods=["post"], url_path="set-exam-period")
    def set_exam_period(self, request, pk=None):
        semester = self.get_object()
        user = request.user
        admin_prof = getattr(user, "admin_profile", None)
        is_school_admin = user.role == "admin" and admin_prof and admin_prof.level == "school"
        is_system_admin = user.is_superuser or (admin_prof and admin_prof.level in ["system", "university"]) or (user.is_staff and not admin_prof)

        if not (is_school_admin or is_system_admin):
            return Response(
                {"error": "Only school administrators can define the school-wide examination period."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if is_school_admin and admin_prof.scope_school_id and semester.session.school_id != admin_prof.scope_school_id:
            return Response(
                {"error": "School administrators can only set examination periods for their assigned school."},
                status=status.HTTP_403_FORBIDDEN,
            )

        exam_start_date = request.data.get("exam_start_date")
        exam_end_date = request.data.get("exam_end_date")

        if not exam_start_date or not exam_end_date:
            return Response(
                {"error": "Both exam_start_date and exam_end_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if str(exam_start_date) >= str(exam_end_date):
            return Response(
                {"error": "Exam start date must be before end date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if semester.start_date and str(exam_start_date) < str(semester.start_date):
            return Response(
                {"error": "Exam period cannot start before semester start date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if semester.end_date and str(exam_end_date) > str(semester.end_date):
            return Response(
                {"error": "Exam period cannot end after semester end date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        semester.exam_start_date = exam_start_date
        semester.exam_end_date = exam_end_date
        semester.save(update_fields=["exam_start_date", "exam_end_date"])
        return Response(SemesterSerializer(semester).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Manage faculty-specific exam periods for a semester")
    @action(detail=True, methods=["get", "post", "delete"], url_path="faculty-exam-periods")
    def faculty_exam_periods(self, request, pk=None):
        semester = self.get_object()
        school = semester.session.school

        if request.method.lower() == "get":
            faculty_id = request.query_params.get("faculty")
            qs = FacultyExamPeriod.objects.filter(semester=semester)
            if faculty_id:
                qs = qs.filter(faculty_id=faculty_id)
            return Response(FacultyExamPeriodSerializer(qs, many=True).data)

        user = request.user
        admin_prof = getattr(user, "admin_profile", None)
        is_faculty_admin = user.role == "admin" and admin_prof and admin_prof.level == "faculty"
        is_school_admin = user.role == "admin" and admin_prof and admin_prof.level == "school"
        is_system_admin = user.is_superuser or (admin_prof and admin_prof.level in ["system", "university"]) or (user.is_staff and not admin_prof)

        perm = GenerationScopePermission.objects.filter(school=school).first()
        allow_faculty_exam = bool(perm and perm.allow_faculty_exam_period)

        if not (is_faculty_admin or is_school_admin or is_system_admin):
            return Response(
                {"error": "Only faculty or school administrators can manage faculty examination periods."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if is_faculty_admin and not allow_faculty_exam:
            return Response(
                {"error": "Faculty-specific examination periods are not permitted by the school administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method.lower() == "delete":
            faculty_id = request.data.get("faculty") or request.query_params.get("faculty")
            if is_faculty_admin and admin_prof.scope_faculty_id:
                faculty_id = admin_prof.scope_faculty_id
            if not faculty_id:
                return Response({"error": "Faculty ID required."}, status=status.HTTP_400_BAD_REQUEST)
            FacultyExamPeriod.objects.filter(semester=semester, faculty_id=faculty_id).delete()
            return Response({"status": "deleted"}, status=status.HTTP_200_OK)

        # POST: Create or Update
        faculty_id = request.data.get("faculty")
        if is_faculty_admin and admin_prof.scope_faculty_id:
            faculty_id = admin_prof.scope_faculty_id
        if not faculty_id:
            return Response({"error": "Faculty ID required."}, status=status.HTTP_400_BAD_REQUEST)

        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        fep, _ = FacultyExamPeriod.objects.get_or_create(
            semester=semester,
            faculty_id=faculty_id,
            defaults={"start_date": start_date, "end_date": end_date, "created_by": admin_prof},
        )
        serializer = FacultyExamPeriodSerializer(
            fep,
            data={"semester": semester.id, "faculty": faculty_id, "start_date": start_date, "end_date": end_date},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=admin_prof)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(summary="Get effective examination period for a given faculty or department")
    @action(detail=True, methods=["get"], url_path="effective-exam-period")
    def effective_exam_period(self, request, pk=None):
        semester = self.get_object()
        faculty_id = request.query_params.get("faculty")
        department_id = request.query_params.get("department")

        from hierarchy.models import Faculty, Department
        faculty = Faculty.objects.filter(id=faculty_id).first() if faculty_id else None
        department = Department.objects.filter(id=department_id).first() if department_id else None

        school = semester.session.school
        perm = GenerationScopePermission.objects.filter(school=school).first()
        allow_faculty_exam = bool(perm and perm.allow_faculty_exam_period)

        start_date, end_date, source, fep = get_effective_exam_period(
            semester, faculty=faculty, department=department
        )

        return Response({
            "semester_id": semester.id,
            "school_id": school.id,
            "school_exam_start_date": semester.exam_start_date,
            "school_exam_end_date": semester.exam_end_date,
            "allow_faculty_exam_period": allow_faculty_exam,
            "effective_start_date": start_date,
            "effective_end_date": end_date,
            "source": source,
            "is_set": bool(start_date and end_date),
            "faculty_id": faculty.id if faculty else None,
            "faculty_name": faculty.name if faculty else None,
        })



class TimetableEntryViewSet(viewsets.ModelViewSet):
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        if user.role == "student" and hasattr(user, "student_profile"):
            from courses.services import get_visible_courses_for_student
            visible_courses = get_visible_courses_for_student(user.student_profile)
            return TimetableEntry.objects.filter(
                Q(course__in=visible_courses) | Q(entry_type="event")
            ).distinct()

        if user.role == "lecturer" and hasattr(user, "lecturer_profile"):
            return TimetableEntry.objects.filter(
                Q(course__lecturers=user.lecturer_profile) | Q(entry_type="event")
            ).distinct()

        dept_qs = get_user_scope_departments(user)
        fac_qs = get_user_scope_faculties(user)
        sch_qs = get_user_scope_schools(user)

        qs = TimetableEntry.objects.filter(
            Q(course__owning_department__in=dept_qs)
            | Q(course__owning_faculty__in=fac_qs)
            | Q(course__owning_school__in=sch_qs)
            | Q(venue__owning_department__in=dept_qs)
            | Q(venue__owning_faculty__in=fac_qs)
            | Q(venue__owning_school__in=sch_qs)
            | Q(entry_type="event")
        ).distinct()

        semester_param = self.request.query_params.get("semester")
        if semester_param:
            qs = qs.filter(semester_id=semester_param)
        department_param = self.request.query_params.get("department")
        if department_param:
            qs = qs.filter(
                Q(course__owning_department_id=department_param)
                | Q(course__target_program__department_id=department_param)
                | Q(entry_type="event")
            )
        faculty_param = self.request.query_params.get("faculty")
        if faculty_param:
            qs = qs.filter(
                Q(course__owning_faculty_id=faculty_param)
                | Q(course__owning_department__faculty_id=faculty_param)
                | Q(entry_type="event")
            )
        program_param = self.request.query_params.get("program")
        if program_param and str(program_param).upper() != "ALL":
            from hierarchy.models import Program
            prog = Program.objects.filter(id=program_param).first()
            if prog:
                qs = qs.filter(
                    Q(entry_type="event")
                    | Q(course__target_program_id=program_param)
                    | Q(course__access_grants__target_program_id=program_param, course__access_grants__status="approved")
                    | (
                        Q(course__owning_department_id=prog.department_id)
                        & (Q(course__target_program_id__isnull=True) | Q(course__target_program_id=program_param))
                    )
                    | (
                        Q(course__owning_level__in=["faculty", "school", "general"])
                        & (
                            Q(course__owning_faculty_id=prog.department.faculty_id)
                            | Q(course__owning_school_id=prog.department.faculty.school_id)
                            | Q(course__owning_level="general")
                        )
                    )
                )
            else:
                qs = qs.filter(
                    Q(entry_type="event")
                    | Q(course__target_program_id=program_param)
                    | Q(course__owning_level__in=["faculty", "school", "general"])
                )
        level_param = self.request.query_params.get("level")
        if level_param:
            qs = qs.filter(Q(course__level=level_param) | Q(entry_type="event"))
        entry_type_param = self.request.query_params.get("entry_type")
        if entry_type_param:
            if "," in entry_type_param:
                qs = qs.filter(entry_type__in=[t.strip() for t in entry_type_param.split(",")])
            else:
                qs = qs.filter(entry_type=entry_type_param)
        exclude_entry_type = self.request.query_params.get("exclude_entry_type")
        if exclude_entry_type:
            qs = qs.exclude(entry_type=exclude_entry_type)

        include_pending = self.request.query_params.get("include_pending") in ["true", "1", True]
        if not include_pending:
            qs = qs.exclude(status=TimetableEntry.Status.PENDING_APPROVAL)

        return qs.distinct()

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPasswordResetDone(), IsAdminUserRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.admin_profile)

    def create(self, request, *args, **kwargs):
        admin_prof = getattr(request.user, "admin_profile", None)
        if admin_prof and getattr(admin_prof, "is_exam_officer", False):
            entry_type = request.data.get("entry_type")
            if entry_type != TimetableEntry.EntryType.EXAM:
                return Response(
                    {"detail": "Exam Officers can only schedule exam entries."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        pending_discrepancy = serializer.context.get("pending_discrepancy")
        if pending_discrepancy:
            return Response(
                {
                    "outcome": "ROUTE_APPROVAL",
                    "message": "Booking touches a venue outside your scope and has been routed for approval.",
                    "discrepancy_request_id": pending_discrepancy.id,
                    "routed_to_admin_id": pending_discrepancy.routed_to_id,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @extend_schema(summary="Trigger recurrence materialization into LectureSessions", responses={200: LectureSessionSerializer(many=True)})
    @action(detail=True, methods=["post"])
    def materialize(self, request, pk=None):
        entry = self.get_object()
        sessions = materialize_timetable_entry(entry)
        serializer = LectureSessionSerializer(sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LectureSessionViewSet(viewsets.ModelViewSet):
    serializer_class = LectureSessionSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        qs = LectureSession.objects.none()

        if user.role == "student" and hasattr(user, "student_profile"):
            student = user.student_profile
            from courses.services import get_visible_courses_for_student
            visible_courses = get_visible_courses_for_student(student)
            qs = LectureSession.objects.filter(
                Q(timetable_entry__course__in=visible_courses)
                | Q(timetable_entry__entry_type="event")
            ).distinct()

            # Non-class rep students cannot view previous past lectures
            if not student.is_class_rep:
                qs = qs.filter(session_date__gte=date.today())
        elif user.role == "lecturer" and hasattr(user, "lecturer_profile"):
            qs = LectureSession.objects.filter(
                Q(timetable_entry__course__lecturers=user.lecturer_profile)
                | Q(timetable_entry__entry_type="event")
            ).distinct()
        else:
            dept_qs = get_user_scope_departments(user)
            fac_qs = get_user_scope_faculties(user)
            sch_qs = get_user_scope_schools(user)
            qs = LectureSession.objects.filter(
                Q(timetable_entry__course__owning_department__in=dept_qs)
                | Q(timetable_entry__course__owning_faculty__in=fac_qs)
                | Q(timetable_entry__course__owning_school__in=sch_qs)
                | Q(venue__owning_department__in=dept_qs)
                | Q(venue__owning_faculty__in=fac_qs)
                | Q(venue__owning_school__in=sch_qs)
                | Q(timetable_entry__entry_type="event")
            ).distinct()

        # Query parameters filters
        session_date = self.request.query_params.get("session_date") or self.request.query_params.get("date")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        status_param = self.request.query_params.get("status")
        semester_param = self.request.query_params.get("semester")
        program_param = self.request.query_params.get("program")
        level_param = self.request.query_params.get("level")
        entry_type_param = self.request.query_params.get("entry_type")

        if session_date:
            qs = qs.filter(session_date=session_date)
        if start_date:
            qs = qs.filter(session_date__gte=start_date)
        if end_date:
            qs = qs.filter(session_date__lte=end_date)
        if status_param and status_param != "all":
            qs = qs.filter(status=status_param)
        if semester_param:
            qs = qs.filter(timetable_entry__semester_id=semester_param)
        department_param = self.request.query_params.get("department")
        if department_param:
            qs = qs.filter(
                Q(timetable_entry__course__owning_department_id=department_param)
                | Q(timetable_entry__course__target_program__department_id=department_param)
                | Q(timetable_entry__entry_type="event")
            )
        faculty_param = self.request.query_params.get("faculty")
        if faculty_param:
            qs = qs.filter(
                Q(timetable_entry__course__owning_faculty_id=faculty_param)
                | Q(timetable_entry__course__owning_department__faculty_id=faculty_param)
                | Q(timetable_entry__entry_type="event")
            )
        if program_param and str(program_param).upper() != "ALL":
            from hierarchy.models import Program
            prog = Program.objects.filter(id=program_param).first()
            if prog:
                qs = qs.filter(
                    Q(timetable_entry__entry_type="event")
                    | Q(timetable_entry__course__target_program_id=program_param)
                    | Q(timetable_entry__course__access_grants__target_program_id=program_param, timetable_entry__course__access_grants__status="approved")
                    | (
                        Q(timetable_entry__course__owning_department_id=prog.department_id)
                        & (Q(timetable_entry__course__target_program_id__isnull=True) | Q(timetable_entry__course__target_program_id=program_param))
                    )
                    | (
                        Q(timetable_entry__course__owning_level__in=["faculty", "school", "general"])
                        & (
                            Q(timetable_entry__course__owning_faculty_id=prog.department.faculty_id)
                            | Q(timetable_entry__course__owning_school_id=prog.department.faculty.school_id)
                            | Q(timetable_entry__course__owning_level="general")
                        )
                    )
                )
            else:
                qs = qs.filter(
                    Q(timetable_entry__entry_type="event")
                    | Q(timetable_entry__course__target_program_id=program_param)
                    | Q(timetable_entry__course__owning_level__in=["faculty", "school", "general"])
                )
        if level_param:
            qs = qs.filter(Q(timetable_entry__course__level=level_param) | Q(timetable_entry__entry_type="event"))
        if entry_type_param:
            if "," in entry_type_param:
                qs = qs.filter(timetable_entry__entry_type__in=[t.strip() for t in entry_type_param.split(",")])
            else:
                qs = qs.filter(timetable_entry__entry_type=entry_type_param)
        exclude_entry_type = self.request.query_params.get("exclude_entry_type")
        if exclude_entry_type:
            qs = qs.exclude(timetable_entry__entry_type=exclude_entry_type)

        return qs.order_by("session_date", "session_start_time")

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy", "cancel"]:
            return [IsAuthenticated(), IsPasswordResetDone()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        session = self.get_object()

        # 1. Past sessions can NEVER be shifted
        now = timezone.now()
        dt = datetime.datetime.combine(session.session_date, session.session_end_time)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        if dt <= now:
            return Response(
                {"detail": "Past lectures/events cannot be shifted or rescheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Check jurisdiction: scope-level admin, originating creator, superuser, OR assigned lecturer
        admin_profile = getattr(request.user, "admin_profile", None)
        lecturer_profile = getattr(request.user, "lecturer_profile", None)
        is_authorized = False
        if request.user.is_superuser:
            is_authorized = True
        elif request.user.role == "lecturer" and lecturer_profile:
            course = getattr(session.timetable_entry, "course", None)
            if course and course.lecturers.filter(id=lecturer_profile.id).exists():
                is_authorized = True
        elif admin_profile:
            if getattr(admin_profile, "is_exam_officer", False):
                return Response(
                    {"detail": "Exam Officers cannot modify lecture sessions."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            from accounts.models import AdminOfficer
            if admin_profile.level == AdminOfficer.Level.SCHOOL:
                is_authorized = True
            elif session.timetable_entry.created_by_id in (admin_profile.id, getattr(admin_profile, "user_id", None)):
                is_authorized = True
            elif admin_profile.level == AdminOfficer.Level.FACULTY and admin_profile.scope_faculty_id:
                dept = getattr(session.timetable_entry.course, "owning_department", None)
                if dept and dept.faculty_id == admin_profile.scope_faculty_id:
                    is_authorized = True
                elif not session.timetable_entry.course:
                    if session.venue and getattr(session.venue, "owning_faculty_id", None) == admin_profile.scope_faculty_id:
                        is_authorized = True
                    elif session.timetable_entry.target_program and getattr(getattr(session.timetable_entry.target_program, "department", None), "faculty_id", None) == admin_profile.scope_faculty_id:
                        is_authorized = True
                    elif session.timetable_entry.entry_type == "event":
                        is_authorized = True
            elif admin_profile.level == AdminOfficer.Level.DEPARTMENT and admin_profile.scope_department_id:
                if getattr(session.timetable_entry.course, "owning_department_id", None) == admin_profile.scope_department_id:
                    is_authorized = True
                elif not session.timetable_entry.course:
                    if session.venue and getattr(session.venue, "owning_department_id", None) == admin_profile.scope_department_id:
                        is_authorized = True
                    elif session.timetable_entry.target_program and getattr(session.timetable_entry.target_program, "department_id", None) == admin_profile.scope_department_id:
                        is_authorized = True
                    elif session.timetable_entry.entry_type == "event":
                        is_authorized = True

        if not is_authorized:
            return Response(
                {
                    "detail": "You do not have administrative jurisdiction to shift this session instance."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(session, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        target_venue = serializer.validated_data.get("venue", session.venue)
        target_date = serializer.validated_data.get("session_date", session.session_date)
        target_start = serializer.validated_data.get("session_start_time", session.session_start_time)
        target_end = serializer.validated_data.get("session_end_time", session.session_end_time)

        # Disallow rescheduling / shifting to past
        dt_target = datetime.datetime.combine(target_date, target_end)
        if timezone.is_naive(dt_target):
            dt_target = timezone.make_aware(dt_target)
        if dt_target <= now:
            return Response(
                {"detail": "Cannot shift or reschedule a session to a past date or time."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check clash if venue, date, or time is being modified
        if (
            target_venue != session.venue
            or target_date != session.session_date
            or target_start != session.session_start_time
            or target_end != session.session_end_time
        ):
            from .conflict_engine import check_venue_overlap

            conflicts = check_venue_overlap(
                venue=target_venue,
                date=target_date,
                start_time=target_start,
                end_time=target_end,
                exclude_session_id=session.id,
            )
            if conflicts:
                return Response(
                    {
                        "detail": "Proposed venue and time conflict with an existing booking.",
                        "conflicts": conflicts,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if "status" not in serializer.validated_data:
                serializer.validated_data["status"] = LectureSession.Status.SHIFTED

        updated_session = serializer.save()

        # Dispatch SESSION_SHIFTED notification
        if updated_session.status == LectureSession.Status.SHIFTED:
            try:
                from notifications.models import Notification
                from notifications.services import dispatch_event_notification
                from accounts.models import Student

                course = updated_session.timetable_entry.course
                if course:
                    notified_user_ids = set()

                    # 1. Notify assigned lecturers (including initiating lecturer for confirmation)
                    for lecturer in course.lecturers.all():
                        if lecturer.user and lecturer.user.id not in notified_user_ids:
                            dispatch_event_notification(
                                recipient=lecturer.user,
                                notification_type=Notification.NotificationType.SESSION_SHIFTED,
                                title=f"Session Shifted: {course.code}",
                                body=f"Session for {course.code} on {updated_session.session_date} was shifted to {updated_session.venue.name} ({updated_session.session_start_time.strftime('%H:%M')} - {updated_session.session_end_time.strftime('%H:%M')}).",
                                related_model="LectureSession",
                                related_id=updated_session.id,
                            )
                            notified_user_ids.add(lecturer.user.id)

                    # Also notify requesting user if lecturer
                    if request.user.is_authenticated and request.user.id not in notified_user_ids:
                        dispatch_event_notification(
                            recipient=request.user,
                            notification_type=Notification.NotificationType.SESSION_SHIFTED,
                            title=f"Session Shifted: {course.code}",
                            body=f"Session for {course.code} on {updated_session.session_date} was successfully shifted to {updated_session.venue.name} ({updated_session.session_start_time.strftime('%H:%M')} - {updated_session.session_end_time.strftime('%H:%M')}).",
                            related_model="LectureSession",
                            related_id=updated_session.id,
                        )
                        notified_user_ids.add(request.user.id)

                    # 2. Notify class reps (target program, owning department, or access-granted departments)
                    from django.db.models import Q
                    rep_conds = Q()
                    if course.target_program_id:
                        rep_conds |= Q(program_id=course.target_program_id)
                    if course.owning_department_id:
                        rep_conds |= Q(department_id=course.owning_department_id)

                    granted_depts = course.access_grants.filter(status="approved").values_list("granted_to_department_id", flat=True)
                    if granted_depts:
                        rep_conds |= Q(department_id__in=granted_depts)

                    class_reps = Student.objects.filter(is_class_rep=True, level=course.level).filter(rep_conds).distinct()
                    for rep in class_reps:
                        if rep.user and rep.user.id not in notified_user_ids:
                            dispatch_event_notification(
                                recipient=rep.user,
                                notification_type=Notification.NotificationType.SESSION_SHIFTED,
                                title=f"Lecture Shifted: {course.code}",
                                body=f"Lecture for {course.code} on {updated_session.session_date} was shifted to {updated_session.venue.name} ({updated_session.session_start_time.strftime('%H:%M')} - {updated_session.session_end_time.strftime('%H:%M')}).",
                                related_model="LectureSession",
                                related_id=updated_session.id,
                            )
                            notified_user_ids.add(rep.user.id)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to dispatch session shift notification: {e}")

        return Response(serializer.data)

    @extend_schema(summary="Cancel a lecture session instance", responses={200: LectureSessionSerializer})
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        session = self.get_object()

        admin_profile = getattr(request.user, "admin_profile", None)
        lecturer_profile = getattr(request.user, "lecturer_profile", None)
        is_authorized = False
        if request.user.is_superuser:
            is_authorized = True
        elif request.user.role == "lecturer" and lecturer_profile:
            course = getattr(session.timetable_entry, "course", None)
            if course and course.lecturers.filter(id=lecturer_profile.id).exists():
                is_authorized = True
        elif admin_profile:
            if getattr(admin_profile, "is_exam_officer", False):
                return Response(
                    {"detail": "Exam Officers cannot cancel lecture sessions."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            from accounts.models import AdminOfficer
            if admin_profile.level == AdminOfficer.Level.SCHOOL:
                is_authorized = True
            elif session.timetable_entry.created_by_id in (admin_profile.id, getattr(admin_profile, "user_id", None)):
                is_authorized = True
            elif admin_profile.level == AdminOfficer.Level.FACULTY and admin_profile.scope_faculty_id:
                dept = getattr(session.timetable_entry.course, "owning_department", None)
                if dept and dept.faculty_id == admin_profile.scope_faculty_id:
                    is_authorized = True
                elif not session.timetable_entry.course:
                    if session.venue and getattr(session.venue, "owning_faculty_id", None) == admin_profile.scope_faculty_id:
                        is_authorized = True
                    elif session.timetable_entry.target_program and getattr(getattr(session.timetable_entry.target_program, "department", None), "faculty_id", None) == admin_profile.scope_faculty_id:
                        is_authorized = True
                    elif session.timetable_entry.entry_type == "event":
                        is_authorized = True
            elif admin_profile.level == AdminOfficer.Level.DEPARTMENT and admin_profile.scope_department_id:
                if getattr(session.timetable_entry.course, "owning_department_id", None) == admin_profile.scope_department_id:
                    is_authorized = True
                elif not session.timetable_entry.course:
                    if session.venue and getattr(session.venue, "owning_department_id", None) == admin_profile.scope_department_id:
                        is_authorized = True
                    elif session.timetable_entry.target_program and getattr(session.timetable_entry.target_program, "department_id", None) == admin_profile.scope_department_id:
                        is_authorized = True
                    elif session.timetable_entry.entry_type == "event":
                        is_authorized = True

        if not is_authorized:
            return Response(
                {"detail": "You do not have jurisdiction to cancel this session instance."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if session.status == LectureSession.Status.CANCELLED:
            return Response({"detail": "Session is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get("reason", "")
        session.status = LectureSession.Status.CANCELLED
        session.save(update_fields=["status"])

        try:
            from notifications.models import Notification
            from notifications.services import dispatch_event_notification
            from accounts.models import Student

            course = session.timetable_entry.course
            if course:
                body_msg = f"Lecture for {course.code} on {session.session_date} ({session.session_start_time.strftime('%H:%M')} - {session.session_end_time.strftime('%H:%M')}) has been CANCELLED."
                if reason:
                    body_msg += f" Reason: {reason}"

                for lecturer in course.lecturers.all():
                    if lecturer.user_id != request.user.id:
                        dispatch_event_notification(
                            recipient=lecturer.user,
                            notification_type=Notification.NotificationType.SESSION_CANCELLED,
                            title=f"Lecture Cancelled: {course.code}",
                            body=body_msg,
                            related_model="LectureSession",
                            related_id=session.id,
                        )
                class_reps = Student.objects.filter(is_class_rep=True, level=course.level)
                if course.target_program_id:
                    class_reps = class_reps.filter(program_id=course.target_program_id)
                elif course.owning_department_id:
                    class_reps = class_reps.filter(department_id=course.owning_department_id)
                for rep in class_reps:
                    dispatch_event_notification(
                        recipient=rep.user,
                        notification_type=Notification.NotificationType.SESSION_CANCELLED,
                        title=f"Lecture Cancelled: {course.code}",
                        body=body_msg,
                        related_model="LectureSession",
                        related_id=session.id,
                    )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to dispatch session cancel notification: {e}")

        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)


class ExamSittingViewSet(viewsets.ModelViewSet):
    serializer_class = ExamSittingSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        dept_qs = get_user_scope_departments(user)
        return ExamSitting.objects.filter(
            Q(timetable_entry__course__owning_department__in=dept_qs)
            | Q(timetable_entry__venue__owning_department__in=dept_qs)
        ).distinct()

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPasswordResetDone(), IsAdminUserRole()]
        return super().get_permissions()


def infer_optimizer_config_for_scope(
    scope_type: str,
    total_occurrences: int,
    data: Optional[Dict[str, Any]] = None,
) -> OptimizerConfig:
    """
    Infers optimal Genetic Algorithm hyperparameters based on the target scope level
    and problem occurrence scale, allowing explicit user overrides if provided.
    """
    data = data or {}

    if scope_type == "department":
        base_pop = 60
        base_gens = 120
        base_patience = 30
        base_mut = 0.08
    elif scope_type == "faculty":
        base_pop = 120 if total_occurrences >= 150 else 80
        base_gens = 250
        base_patience = 45
        base_mut = 0.08
    else:  # "school"
        base_pop = 180 if total_occurrences >= 300 else 120
        base_gens = 350
        base_patience = 60
        base_mut = 0.07

    return OptimizerConfig(
        population_size=data.get("population_size") or base_pop,
        max_generations=data.get("max_generations") or base_gens,
        mutation_rate=data.get("mutation_rate") or base_mut,
        patience=data.get("stagnation_limit") or base_patience,
    )


class TimetableGenerationViewSet(viewsets.ViewSet):
    """
    Automated timetable generation and discrepancy preview engine using Genetic Algorithm.
    """

    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanGenerateTimetable]

    @extend_schema(
        summary="Generate a weekly timetable using Genetic Algorithm",
        request=GenerateTimetableRequestSerializer,
        responses={200: TimetableGenerationRunDetailSerializer},
    )
    def create(self, request):
        serializer = GenerateTimetableRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        semester_id = data["semester_id"]
        scope_type = data["scope_type"]
        scope_id = data["scope_id"]

        semester = Semester.objects.filter(id=semester_id).select_related("session__school").first()
        if not semester:
            return Response({"error": "Semester not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check generation permission
        is_allowed, reason = check_scope_generation_permission(request.user, semester, scope_type, scope_id)
        if not is_allowed:
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)

        # Build problem
        try:
            problem = build_scheduling_problem_from_db(
                semester_id=semester_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to prepare scheduling data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Configure optimizer - auto-inferred from scope level and occurrence scale
        config = infer_optimizer_config_for_scope(
            scope_type=scope_type,
            total_occurrences=len(problem.occurrences),
            data=data,
        )

        # Execute optimization
        result = generate_timetable(problem, config=config)

        # Save run record
        now = datetime.datetime.now(datetime.timezone.utc)
        run = TimetableGenerationRun.objects.create(
            semester=semester,
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name=problem.scope_name,
            status=TimetableGenerationRun.Status.COMPLETED,
            result_status=result.status.lower(),
            hard_conflicts_count=result.hard_conflicts_count,
            student_conflicts_count=result.evaluation.student_conflicts,
            lecturer_conflicts_count=result.evaluation.lecturer_conflicts,
            venue_conflicts_count=result.evaluation.venue_conflicts,
            daily_limit_violations_count=result.evaluation.daily_limit_violations,
            occurrence_day_violations_count=result.evaluation.occurrence_day_violations,
            capacity_penalty=result.evaluation.capacity_penalty,
            fitness_score=result.fitness,
            conflict_report=result.conflict_report,
            generation_metrics={
                "generations_run": result.generation_count,
                "runtime_seconds": result.runtime_seconds,
                "elapsed_seconds": result.runtime_seconds,
                "occurrences_total": problem.total_occurrences,
            },
            assignments_payload=result.assignments_payload,
            initiated_by=request.user,
            completed_at=now,
        )

        # If publish_immediately was requested
        if data.get("publish_immediately", False):
            publish_generation_run(run, created_by_admin=request.user)

        return Response(
            TimetableGenerationRunDetailSerializer(run).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(summary="List past timetable generation runs", responses={200: TimetableGenerationRunSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="runs")
    def list_runs(self, request):
        qs = TimetableGenerationRun.objects.select_related("semester__session__school", "initiated_by")
        user = request.user
        if not (user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile"))):
            if hasattr(user, "admin_profile") and user.admin_profile.level == "school":
                qs = qs.filter(semester__session__school=user.admin_profile.scope_school)

        semester_id = request.query_params.get("semester")
        if semester_id:
            qs = qs.filter(semester_id=semester_id)
        scope_type = request.query_params.get("scope_type")
        if scope_type:
            qs = qs.filter(scope_type=scope_type)
        scope_id = request.query_params.get("scope_id")
        if scope_id:
            qs = qs.filter(scope_id=scope_id)
        if user.id:
            qs = qs.filter(initiated_by_id=user.id)

        return Response(TimetableGenerationRunSerializer(qs[:50], many=True).data)

    @extend_schema(summary="Get specific generation run detail and conflict diagnostics", responses={200: TimetableGenerationRunDetailSerializer})
    @action(detail=False, methods=["get"], url_path="runs/(?P<run_id>[^/.]+)")
    def get_run(self, request, run_id=None):
        run = TimetableGenerationRun.objects.filter(id=run_id).select_related("semester__session__school", "initiated_by").first()
        if not run:
            return Response({"error": "Generation run not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(TimetableGenerationRunDetailSerializer(run).data)

    @extend_schema(summary="Publish a generated timetable run into live timetable entries")
    @action(detail=False, methods=["post"], url_path="runs/(?P<run_id>[^/.]+)/publish")
    def publish_run(self, request, run_id=None):
        run = TimetableGenerationRun.objects.filter(id=run_id).select_related("semester__session__school").first()
        if not run:
            return Response({"error": "Generation run not found."}, status=status.HTTP_404_NOT_FOUND)

        is_allowed, reason = check_scope_generation_permission(request.user, run.semester, run.scope_type, run.scope_id)
        if not is_allowed:
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)

        try:
            pub_result = publish_generation_run(run, created_by_admin=request.user)
            return Response(pub_result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Publish failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Get or update generation permissions for a school", responses={200: GenerationScopePermissionSerializer})
    @action(detail=False, methods=["get", "patch"], url_path="permissions")
    def permissions_endpoint(self, request):
        if request.method.lower() == "patch":
            admin_prof = getattr(request.user, "admin_profile", None)
            is_school_admin = request.user.role == "admin" and admin_prof and admin_prof.level == "school"
            is_system_admin = (
                request.user.is_superuser
                or (admin_prof and admin_prof.level in ["system", "university"])
                or (request.user.is_staff and not admin_prof)
            )

            if not (is_school_admin or is_system_admin):
                return Response(
                    {"error": "Only school administrators can configure timetable generation permissions."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            school_id = request.data.get("school")
            if not school_id:
                if is_school_admin and admin_prof.scope_school_id:
                    school_id = admin_prof.scope_school_id
                else:
                    return Response({"error": "School ID required."}, status=status.HTTP_400_BAD_REQUEST)

            if is_school_admin and admin_prof.scope_school_id:
                if int(school_id) != admin_prof.scope_school_id:
                    return Response(
                        {"error": "School administrators can only configure timetable generation permissions for their assigned school."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            perm, _ = GenerationScopePermission.objects.get_or_create(school_id=school_id)
            serializer = GenerationScopePermissionSerializer(perm, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            # If allow_faculty_exam_period is revoked, clear custom faculty exam periods for this school
            if not perm.allow_faculty_exam_period:
                FacultyExamPeriod.objects.filter(faculty__school_id=school_id).delete()
            return Response(serializer.data)

        # GET
        user = request.user
        school_id = request.query_params.get("school")
        if not school_id:
            if hasattr(user, "admin_profile") and user.admin_profile.scope_school_id:
                school_id = user.admin_profile.scope_school_id
            elif hasattr(user, "admin_profile") and user.admin_profile.scope_faculty:
                school_id = user.admin_profile.scope_faculty.school_id
            elif hasattr(user, "admin_profile") and user.admin_profile.scope_department and user.admin_profile.scope_department.faculty:
                school_id = user.admin_profile.scope_department.faculty.school_id

        if not school_id:
            return Response({"error": "School ID required."}, status=status.HTTP_400_BAD_REQUEST)

        perm, _ = GenerationScopePermission.objects.get_or_create(school_id=school_id)
        return Response(GenerationScopePermissionSerializer(perm).data)

    @extend_schema(summary="Export scheduling problem dataset as hierarchical JSON or CSV", request=GenerateTimetableRequestSerializer)
    @action(detail=False, methods=["get", "post"], url_path="export-problem")
    def export_problem(self, request):
        if request.method.lower() == "post":
            serializer = GenerateTimetableRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            semester_id = data["semester_id"]
            scope_type = data["scope_type"]
            scope_id = data["scope_id"]
            export_format = request.data.get("format", "json").lower()
        else:
            semester_id = request.query_params.get("semester_id") or request.query_params.get("semester")
            scope_type = request.query_params.get("scope_type", "school")
            scope_id = request.query_params.get("scope_id")
            export_format = request.query_params.get("format", "json").lower()
            if not semester_id or not scope_id:
                return Response(
                    {"error": "Both semester_id and scope_id are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        semester = Semester.objects.filter(id=semester_id).select_related("session__school").first()
        if not semester:
            return Response({"error": "Semester not found."}, status=status.HTTP_404_NOT_FOUND)

        is_allowed, reason = check_scope_generation_permission(request.user, semester, scope_type, scope_id)
        if not is_allowed:
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)

        try:
            problem = build_scheduling_problem_from_db(
                semester_id=semester_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to prepare scheduling data: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if export_format == "csv":
            csv_content = serialize_problem_to_csv(problem)
            filename = f"scheduling_problem_{scope_type}_{scope_id}_semester_{semester_id}.csv"
            response = HttpResponse(csv_content, content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        json_data = serialize_problem_to_dict(problem)
        return Response(json_data, status=status.HTTP_200_OK)

