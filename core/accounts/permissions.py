# pyrefly: ignore [missing-import]
from hierarchy.models import Department, Faculty, School
from rest_framework.permissions import BasePermission


def get_user_scope_departments(user):
    """
    Resolves the list of department IDs accessible to a user based on their scope.
    School admins get all departments under their school.
    Faculty admins get all departments under their faculty.
    Department admins get their specific department.
    Students and lecturers get their home department.
    """
    if not user.is_authenticated:
        return Department.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return Department.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "school":
            if admin_prof.scope_school:
                return Department.objects.filter(faculty__school=admin_prof.scope_school)
            return Department.objects.none()
        elif admin_prof.level == "faculty":
            if admin_prof.scope_faculty:
                return Department.objects.filter(faculty=admin_prof.scope_faculty)
            return Department.objects.none()
        elif admin_prof.level == "department":
            if admin_prof.scope_department:
                return Department.objects.filter(id=admin_prof.scope_department.id)
            return Department.objects.none()
        return Department.objects.none()

    if user.role == "student" and hasattr(user, "student_profile"):
        return Department.objects.filter(id=user.student_profile.department_id)

    if user.role == "lecturer" and hasattr(user, "lecturer_profile"):
        return Department.objects.filter(id=user.lecturer_profile.department_id)

    return Department.objects.none()


def get_user_scope_faculties(user):
    """
    Resolves faculties accessible to a user.
    """
    if not user.is_authenticated:
        return Faculty.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return Faculty.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "school":
            if admin_prof.scope_school:
                return Faculty.objects.filter(school=admin_prof.scope_school)
            return Faculty.objects.none()
        elif admin_prof.level == "faculty":
            if admin_prof.scope_faculty:
                return Faculty.objects.filter(id=admin_prof.scope_faculty.id)
            return Faculty.objects.none()
        elif admin_prof.level == "department":
            if admin_prof.scope_department:
                return Faculty.objects.filter(id=admin_prof.scope_department.faculty_id)
            return Faculty.objects.none()
        return Faculty.objects.none()

    if user.role == "student" and hasattr(user, "student_profile"):
        return Faculty.objects.filter(id=user.student_profile.department.faculty_id)

    if user.role == "lecturer" and hasattr(user, "lecturer_profile"):
        return Faculty.objects.filter(id=user.lecturer_profile.department.faculty_id)

    return Faculty.objects.none()


def get_user_scope_schools(user):
    """
    Resolves schools accessible to a user.
    """
    if not user.is_authenticated:
        return School.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return School.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "school":
            if admin_prof.scope_school:
                return School.objects.filter(id=admin_prof.scope_school.id)
            return School.objects.none()
        elif admin_prof.level == "faculty":
            if admin_prof.scope_faculty:
                return School.objects.filter(id=admin_prof.scope_faculty.school_id)
            return School.objects.none()
        elif admin_prof.level == "department":
            if admin_prof.scope_department:
                return School.objects.filter(id=admin_prof.scope_department.faculty.school_id)
            return School.objects.none()
        return School.objects.none()

    if user.role == "student" and hasattr(user, "student_profile"):
        return School.objects.filter(id=user.student_profile.department.faculty.school_id)

    if user.role == "lecturer" and hasattr(user, "lecturer_profile"):
        return School.objects.filter(id=user.lecturer_profile.department.faculty.school_id)

    return School.objects.none()


def get_user_scope_admin_officers(user):
    """
    Resolves the list of AdminOfficer instances visible/manageable by a user.
    Rules:
    - An admin officer CANNOT see or perform actions on users of higher level OR SAME level.
    - Superuser: Can see all AdminOfficer instances.
    - School admin: Can see Faculty admins (under scope_school) and Department admins (under scope_school). Excludes other school admins & superusers.
    - Faculty admin: Can see Department admins (under scope_faculty). Excludes faculty admins, school admins, & superusers.
    - Department admin: Cannot see any Admin Officers. Returns AdminOfficer.objects.none().
    """
    from accounts.models import AdminOfficer
    from django.db import models

    if not user.is_authenticated:
        return AdminOfficer.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return AdminOfficer.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "school":
            if admin_prof.scope_school:
                return AdminOfficer.objects.filter(
                    models.Q(level="faculty", scope_faculty__school=admin_prof.scope_school)
                    | models.Q(level="department", scope_department__faculty__school=admin_prof.scope_school)
                )
            return AdminOfficer.objects.filter(level__in=["faculty", "department"])

        elif admin_prof.level == "faculty":
            if admin_prof.scope_faculty:
                return AdminOfficer.objects.filter(
                    level="department",
                    scope_department__faculty=admin_prof.scope_faculty,
                )
            return AdminOfficer.objects.filter(level="department")

        elif admin_prof.level == "department":
            return AdminOfficer.objects.none()

    return AdminOfficer.objects.none()


# pyrefly: ignore [missing-import]
from discrepancies.middleware import set_current_user
# pyrefly: ignore [missing-import]
from hierarchy.models import Department, Faculty, School
from rest_framework import permissions
from rest_framework.permissions import BasePermission


class IsAuthenticated(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        is_auth = super().has_permission(request, view)
        if is_auth and request.user and request.user.is_authenticated:
            set_current_user(request.user)
        return is_auth


class IsPasswordResetDone(BasePermission):
    """
    Blocks authenticated users from accessing endpoints if requires_password_reset is True.
    """
    message = "First-login password reset is required before accessing the system."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        set_current_user(request.user)
        return not request.user.requires_password_reset


class IsAdminUserRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class IsStudentRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "student")


class IsLecturerRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "lecturer")
