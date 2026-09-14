from accounts.permissions import (
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Department, Faculty, Program, School
from .permissions import CanManageDepartment, CanManageFaculty, CanManageProgram, CanManageSchool
from .serializers import DepartmentSerializer, FacultySerializer, ProgramSerializer, SchoolSerializer


class SchoolViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageSchool]

    def get_queryset(self):
        return get_user_scope_schools(self.request.user)


class FacultyViewSet(viewsets.ModelViewSet):
    serializer_class = FacultySerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageFaculty]

    def get_queryset(self):
        return get_user_scope_faculties(self.request.user)


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageDepartment]

    def get_queryset(self):
        return get_user_scope_departments(self.request.user)


class ProgramViewSet(viewsets.ModelViewSet):
    serializer_class = ProgramSerializer
    permission_classes = [IsAuthenticated, IsPasswordResetDone, CanManageProgram]

    def get_queryset(self):
        qs = Program.objects.select_related("department__faculty__school").filter(
            department__in=get_user_scope_departments(self.request.user)
        )
        dept_id = self.request.query_params.get("department")
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_default:
            return Response(
                {"detail": "The default program cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

