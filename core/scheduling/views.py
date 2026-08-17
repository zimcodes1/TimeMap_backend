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

from .models import ExamSitting, LectureSession, TimetableEntry
from .serializers import (
    ExamSittingSerializer,
    LectureSessionSerializer,
    TimetableEntrySerializer,
)
from .services import materialize_timetable_entry


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

        return TimetableEntry.objects.filter(
            Q(course__owning_department__in=dept_qs)
            | Q(course__owning_faculty__in=fac_qs)
            | Q(course__owning_school__in=sch_qs)
            | Q(venue__owning_department__in=dept_qs)
            | Q(venue__owning_faculty__in=fac_qs)
            | Q(venue__owning_school__in=sch_qs)
        ).distinct()

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
            qs = LectureSession.objects.filter(
                Q(timetable_entry__course__owning_department__in=dept_qs)
                | Q(venue__owning_department__in=dept_qs)
            ).distinct()

        # Query parameters filters
        session_date = self.request.query_params.get("session_date") or self.request.query_params.get("date")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        status_param = self.request.query_params.get("status")

        if session_date:
            qs = qs.filter(session_date=session_date)
        if start_date:
            qs = qs.filter(session_date__gte=start_date)
        if end_date:
            qs = qs.filter(session_date__lte=end_date)
        if status_param and status_param != "all":
            qs = qs.filter(status=status_param)

        return qs.order_by("session_date", "session_start_time")


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
