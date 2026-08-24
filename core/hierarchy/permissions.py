from rest_framework import permissions
from rest_framework.permissions import BasePermission


class CanManageSchool(BasePermission):
    """
    Only University-level admins or superusers can create, update, or delete schools.
    Read-only access is permitted for all authenticated users (scoped by get_user_scope_schools).
    """

    message = "Only University level admins or superusers can create, edit, or delete schools."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True
        return bool(
            user.role == "admin"
            and hasattr(user, "admin_profile")
            and user.admin_profile.level == "university"
        )


class CanManageFaculty(BasePermission):
    """
    Only School-level admins or superusers can create, update, or delete faculties.
    Read-only access is permitted for all authenticated users (scoped by get_user_scope_faculties).
    """

    message = "Only School level admins or superusers can create, edit, or delete faculties."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
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


class CanManageDepartment(BasePermission):
    """
    Only Faculty-level admins or superusers can create, update, or delete departments.
    Read-only access is permitted for all authenticated users (scoped by get_user_scope_departments).
    """

    message = "Only Faculty level admins or superusers can create, edit, or delete departments."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
            return True
        return bool(
            user.role == "admin"
            and hasattr(user, "admin_profile")
            and user.admin_profile.level == "faculty"
        )
