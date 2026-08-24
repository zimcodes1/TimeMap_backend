from accounts.permissions import (
    IsPasswordResetDone,
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Department, Faculty, School
from .permissions import CanManageDepartment, CanManageFaculty, CanManageSchool
from .serializers import DepartmentSerializer, FacultySerializer, SchoolSerializer


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
