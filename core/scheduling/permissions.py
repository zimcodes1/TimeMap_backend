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

