from accounts.permissions import IsPasswordResetDone, get_user_scope_departments
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ProgramStudentCount
from .permissions import CanAccessStudentCounts, CanManageStudentCounts
from .serializers import ProgramStudentCountSerializer, StudentCountAnalyticsQuerySerializer
from .services import get_student_count_analytics


class ProgramStudentCountViewSet(viewsets.ModelViewSet):
    serializer_class = ProgramStudentCountSerializer
    permission_classes = [IsPasswordResetDone, CanAccessStudentCounts, CanManageStudentCounts]

    def get_queryset(self):
        return ProgramStudentCount.objects.select_related(
            "program__department__faculty__school", "updated_by"
        ).filter(program__department__in=get_user_scope_departments(self.request.user))

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user.admin_profile)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user.admin_profile)

    @extend_schema(parameters=[StudentCountAnalyticsQuerySerializer])
    @action(detail=False, methods=["get"], url_path="analytics")
    def analytics(self, request):
        queryset = self.get_queryset()
        admin_level = getattr(getattr(request.user, "admin_profile", None), "level", "university")

        level = request.query_params.get("level")
        if level:
            queryset = queryset.filter(level=level)

        program_id = request.query_params.get("program_id")
        if program_id:
            queryset = queryset.filter(program_id=program_id)

        if admin_level == "university":
            school_id = request.query_params.get("school_id")
            if school_id:
                queryset = queryset.filter(program__department__faculty__school_id=school_id)
        elif admin_level == "school":
            faculty_id = request.query_params.get("faculty_id")
            if faculty_id:
                queryset = queryset.filter(program__department__faculty_id=faculty_id)
        elif admin_level == "faculty":
            department_id = request.query_params.get("department_id")
            if department_id:
                queryset = queryset.filter(program__department_id=department_id)

        return Response(get_student_count_analytics(queryset, admin_level), status=status.HTTP_200_OK)
