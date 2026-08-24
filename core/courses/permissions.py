from rest_framework import permissions
from rest_framework.permissions import BasePermission
from .models import Course


class CanManageCourse(BasePermission):
    """
    Permission rules for Courses:
    - SAFE_METHODS (GET, HEAD, OPTIONS): Allowed for all authenticated users (scoped by get_queryset).
    - Write methods (POST, PUT, PATCH, DELETE):
      - Superusers / staff without admin profile: Allowed.
      - University level admin: Blocked (View all, edit none, delete none).
      - School level admin: Allowed ONLY for school-level courses within their assigned school.
      - Faculty level admin: Allowed ONLY for faculty-level courses within their assigned faculty.
      - Department level admin: Allowed ONLY for department-level courses within their assigned department.
    """

    message = "You do not have permission to manage this course. Granted or out-of-scope courses can only be managed by their originating owner."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True

        if user.role == "admin" and hasattr(user, "admin_profile"):
            level = user.admin_profile.level
            if level == "university":
                return False  # System level: edit none, delete none
            return level in ["school", "faculty", "department"]

        return False

    def has_object_permission(self, request, view, obj: Course):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True

        if user.role == "admin" and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            level = admin_prof.level

            if level == "university":
                return False  # Edit none, delete none

            if level == "school":
                return bool(
                    obj.owning_level == Course.OwningLevel.SCHOOL
                    and admin_prof.scope_school_id
                    and obj.owning_school_id == admin_prof.scope_school_id
                )

            if level == "faculty":
                return bool(
                    obj.owning_level == Course.OwningLevel.FACULTY
                    and admin_prof.scope_faculty_id
                    and obj.owning_faculty_id == admin_prof.scope_faculty_id
                )

            if level == "department":
                return bool(
                    obj.owning_level == Course.OwningLevel.DEPARTMENT
                    and admin_prof.scope_department_id
                    and obj.owning_department_id == admin_prof.scope_department_id
                )

        return False


class CanManageCourseGrant(BasePermission):
    """
    Permission rules for Course Access Grants:
    - Superusers, Faculty admins, and Department admins can create, view, approve, and reject grants.
    - School level and University level admins cannot manage access grants ("no access grants since they can only create school-level courses").
    """

    message = "School and University level admins cannot manage course access grants."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True

        if user.role == "admin" and hasattr(user, "admin_profile"):
            level = user.admin_profile.level
            if level in ["university", "school"]:
                return False  # No access grants for school/university level
            return level in ["faculty", "department"]

        return False
