from accounts.permissions import (
    IsAdminUserRole,
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClassRepReport, UnreportedSessionFlag
from .serializers import (
    ClassRepReportSerializer,
    LecturerResponseSerializer,
    UnreportedSessionFlagSerializer,
)
from .services import (
    acknowledge_unreported_flag,
    run_unreported_sessions_sweep,
    submit_lecturer_response,
)


class ClassRepReportViewSet(viewsets.ModelViewSet):
    serializer_class = ClassRepReportSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        qs = ClassRepReport.objects.all()

        if user.role == "student" and hasattr(user, "student_profile"):
            qs = qs.filter(reported_by=user.student_profile)
        elif user.role == "lecturer" and hasattr(user, "lecturer_profile"):
            qs = qs.filter(lecture_session__timetable_entry__course__lecturers=user.lecturer_profile)
        elif user.role == "admin" and hasattr(user, "admin_profile"):
            dept_qs = get_user_scope_departments(user)
            qs = qs.filter(lecture_session__timetable_entry__course__owning_department__in=dept_qs)

        # Filters
        held_param = self.request.query_params.get("held")
        if held_param is not None:
            qs = qs.filter(held=held_param.lower() == "true")

        course_param = self.request.query_params.get("course")
        if course_param:
            qs = qs.filter(lecture_session__timetable_entry__course_id=course_param)

        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(summary="Attach lecturer dispute response to report", request=LecturerResponseSerializer, responses={200: ClassRepReportSerializer})
    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        report = self.get_object()
        serializer = LecturerResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = submit_lecturer_response(
            report=report,
            lecturer_user=request.user,
            response_text=serializer.validated_data["response_text"],
        )
        return Response(ClassRepReportSerializer(updated).data, status=status.HTTP_200_OK)


class UnreportedSessionFlagViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = UnreportedSessionFlagSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone]

    def get_queryset(self):
        user = self.request.user
        if user.role != "admin" or not hasattr(user, "admin_profile"):
            return UnreportedSessionFlag.objects.none()

        dept_qs = get_user_scope_departments(user)
        return UnreportedSessionFlag.objects.filter(
            lecture_session__timetable_entry__course__owning_department__in=dept_qs
        ).distinct()

    @extend_schema(summary="Acknowledge an unreported session flag", responses={200: UnreportedSessionFlagSerializer})
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsPasswordResetDone, IsAdminUserRole])
    def acknowledge(self, request, pk=None):
        flag = self.get_object()
        ack = acknowledge_unreported_flag(flag, request.user)
        return Response(UnreportedSessionFlagSerializer(ack).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Trigger manual unreported session sweep", responses={200: dict})
    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, IsPasswordResetDone, IsAdminUserRole])
    def trigger_sweep(self, request):
        flagged_count = run_unreported_sessions_sweep()
        return Response({"message": f"Sweep completed successfully. Flagged {flagged_count} unreported sessions.", "flagged_count": flagged_count}, status=status.HTTP_200_OK)
