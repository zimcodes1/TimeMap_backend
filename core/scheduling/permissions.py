from rest_framework import permissions
from rest_framework.permissions import BasePermission


class CanManageSessionAndSemester(BasePermission):
    """
    Only School-level admins or superusers can create, update, or delete academic sessions and semesters.
    Read-only access is permitted for all authenticated users.
    """

    message = "Only School level administrators can create, edit, or delete academic sessions and semesters."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True
        return bool(
            user.role == "admin"
            and hasattr(user, "admin_profile")
            and user.admin_profile.level == "school"
        )


class CanGenerateTimetable(BasePermission):
    """
    Controls who can view, trigger, and publish automated timetable generations.
    """

    message = "You do not have permission to generate timetables."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True
        if user.role != "admin" or not hasattr(user, "admin_profile"):
            return False
        return True


class CanManageGenerationPermissions(BasePermission):
    """
    Only Superusers (system-level admins) can configure decentralized generation permissions.
    """

    message = "Only system-level administrators can configure timetable generation permissions."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return user.role == "admin"
        return bool(user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")))


def check_scope_generation_permission(user, semester, scope_type: str, scope_id: int):
    """
    Enforces business logic permissions on generation scope:
      - Superuser: Allowed all scopes.
      - School admin: Allowed for their school, or subordinate faculties/departments.
      - Faculty admin: Allowed for their faculty ONLY IF allow_faculty_generation is True for the school.
      - Department admin: Allowed for their department ONLY IF allow_department_generation is True for the school.
    Returns (is_allowed: bool, reason: str)
    """
    from hierarchy.models import Department, Faculty, School
    from .models import GenerationScopePermission

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return True, ""

    if user.role != "admin" or not hasattr(user, "admin_profile"):
        return False, "Only administrative officers can generate timetables."

    admin_profile = user.admin_profile
    level = admin_profile.level

    if level == "school":
        user_school = admin_profile.scope_school
        if not user_school:
            return False, "Admin officer is not attached to a valid school."

        if scope_type == "school":
            if int(scope_id) != user_school.id:
                return False, "School administrator cannot generate timetables for a different school."
            return True, ""
        elif scope_type == "faculty":
            if not Faculty.objects.filter(id=scope_id, school=user_school).exists():
                return False, "Faculty does not belong to your school."
            return True, ""
        elif scope_type == "department":
            if not Department.objects.filter(id=scope_id, faculty__school=user_school).exists():
                return False, "Department does not belong to your school."
            return True, ""
        return False, f"Unknown scope type: {scope_type}"

    elif level == "faculty":
        user_faculty = admin_profile.scope_faculty
        if not user_faculty:
            return False, "Admin officer is not attached to a valid faculty."

        school = user_faculty.school
        perm = GenerationScopePermission.objects.filter(school=school).first()
        if not perm or not perm.allow_faculty_generation:
            return False, "Faculty-level timetable generation is disabled by the system administrator."

        if scope_type == "faculty":
            if int(scope_id) != user_faculty.id:
                return False, "Faculty administrator cannot generate timetables for another faculty."
            return True, ""
        elif scope_type == "department":
            if not Department.objects.filter(id=scope_id, faculty=user_faculty).exists():
                return False, "Department does not belong to your faculty."
            return True, ""
        return False, "Faculty administrators cannot generate school-wide timetables."

    elif level == "department":
        user_dept = admin_profile.scope_department
        if not user_dept:
            return False, "Admin officer is not attached to a valid department."

        school = user_dept.faculty.school if user_dept.faculty else None
        if not school:
            return False, "Department is not attached to a valid school."

        perm = GenerationScopePermission.objects.filter(school=school).first()
        if not perm or not perm.allow_department_generation:
            return False, "Department-level timetable generation is disabled by the system administrator."

        if scope_type != "department" or int(scope_id) != user_dept.id:
            return False, "Department administrators can only generate timetables for their own department."
        return True, ""

    return False, "Permission denied."


