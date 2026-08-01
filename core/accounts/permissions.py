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

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "school" and admin_prof.scope_school:
            return Department.objects.filter(faculty__school=admin_prof.scope_school)
        elif admin_prof.level == "faculty" and admin_prof.scope_faculty:
            return Department.objects.filter(faculty=admin_prof.scope_faculty)
        elif admin_prof.level == "department" and admin_prof.scope_department:
            return Department.objects.filter(id=admin_prof.scope_department.id)

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

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "school" and admin_prof.scope_school:
            return Faculty.objects.filter(school=admin_prof.scope_school)
        elif admin_prof.level == "faculty" and admin_prof.scope_faculty:
            return Faculty.objects.filter(id=admin_prof.scope_faculty.id)
        elif admin_prof.level == "department" and admin_prof.scope_department:
            return Faculty.objects.filter(id=admin_prof.scope_department.faculty_id)

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

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "school" and admin_prof.scope_school:
            return School.objects.filter(id=admin_prof.scope_school.id)
        elif admin_prof.level == "faculty" and admin_prof.scope_faculty:
            return School.objects.filter(id=admin_prof.scope_faculty.school_id)
        elif admin_prof.level == "department" and admin_prof.scope_department:
            return School.objects.filter(id=admin_prof.scope_department.faculty.school_id)

    if user.role == "student" and hasattr(user, "student_profile"):
        return School.objects.filter(id=user.student_profile.department.faculty.school_id)

    if user.role == "lecturer" and hasattr(user, "lecturer_profile"):
        return School.objects.filter(id=user.lecturer_profile.department.faculty.school_id)

    return School.objects.none()


from discrepancies.middleware import set_current_user
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
