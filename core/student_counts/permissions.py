from rest_framework.permissions import BasePermission, SAFE_METHODS


class CanAccessStudentCounts(BasePermission):
    message = "Only administrative users can access student planning totals."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class CanManageStudentCounts(BasePermission):
    message = "Only department administrators can update their department student total."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        profile = getattr(request.user, "admin_profile", None)
        return bool(profile and profile.level == "department" and profile.scope_department_id)
