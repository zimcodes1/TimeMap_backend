from datetime import date
from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AcademicSession, ExamSitting, LectureSession, Semester, TimetableEntry
from .permissions import CanManageSessionAndSemester
from .serializers import (
    AcademicSessionSerializer,
    ExamSittingSerializer,
    LectureSessionSerializer,
    SemesterSerializer,
    TimetableEntrySerializer,
)
from .services import materialize_timetable_entry


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



class TimetableEntryViewSet(viewsets.ModelViewSet):
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        if user.role == "student" and hasattr(user, "student_profile"):
            dept = user.student_profile.department
            return TimetableEntry.objects.filter(
                Q(course__owning_department=dept)
                | Q(course__owning_faculty=dept.faculty)
                | Q(course__owning_school=dept.faculty.school)
                | Q(course__owning_level="general")
                | Q(venue__owning_department=dept)
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
        ).distinct()

        semester_param = self.request.query_params.get("semester")
        if semester_param:
            qs = qs.filter(semester_id=semester_param)
        program_param = self.request.query_params.get("program")
        if program_param:
            qs = qs.filter(
                Q(course__target_program_id=program_param)
                | Q(course__program_scope="general")
            )
        level_param = self.request.query_params.get("level")
        if level_param:
            qs = qs.filter(course__level=level_param)
        entry_type_param = self.request.query_params.get("entry_type")
        if entry_type_param:
            qs = qs.filter(entry_type=entry_type_param)
        return qs

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPasswordResetDone(), IsAdminUserRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.admin_profile)

    def create(self, request, *args, **kwargs):
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
            dept = user.student_profile.department
            qs = LectureSession.objects.filter(
                Q(timetable_entry__course__owning_department=dept)
                | Q(timetable_entry__course__owning_faculty=dept.faculty)
                | Q(timetable_entry__course__owning_school=dept.faculty.school)
                | Q(timetable_entry__course__owning_level="general")
            ).distinct()

            # Non-class rep students cannot view previous past lectures
            if not user.student_profile.is_class_rep:
                qs = qs.filter(session_date__gte=date.today())
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
        if program_param:
            qs = qs.filter(
                Q(timetable_entry__course__target_program_id=program_param)
                | Q(timetable_entry__course__program_scope="general")
            )
        if level_param:
            qs = qs.filter(timetable_entry__course__level=level_param)
        if entry_type_param:
            qs = qs.filter(timetable_entry__entry_type=entry_type_param)

        return qs.order_by("session_date", "session_start_time")

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), IsPasswordResetDone(), IsAdminUserRole()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        session = self.get_object()

        # Check jurisdiction: creator admin or superuser
        admin_profile = getattr(request.user, "admin_profile", None)
        is_originating_admin = (
            admin_profile is not None
            and session.timetable_entry.created_by_id == admin_profile.id
        )
        if not (is_originating_admin or request.user.is_superuser):
            return Response(
                {
                    "detail": "Only the originating admin who created this schedule has jurisdiction to shift this session instance."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(session, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        target_venue = serializer.validated_data.get("venue", session.venue)
        target_date = serializer.validated_data.get("session_date", session.session_date)
        target_start = serializer.validated_data.get("session_start_time", session.session_start_time)
        target_end = serializer.validated_data.get("session_end_time", session.session_end_time)

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

                course = updated_session.timetable_entry.course
                if course:
                    for lecturer in course.lecturers.all():
                        dispatch_event_notification(
                            recipient=lecturer.user,
                            notification_type=Notification.NotificationType.SESSION_SHIFTED,
                            title=f"Session Shifted: {course.code}",
                            body=f"Session for {course.code} on {updated_session.session_date} was shifted to {updated_session.venue.name} ({updated_session.session_start_time.strftime('%H:%M')} - {updated_session.session_end_time.strftime('%H:%M')}).",
                            related_model="LectureSession",
                            related_id=updated_session.id,
                        )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to dispatch session shift notification: {e}")

        return Response(serializer.data)


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
