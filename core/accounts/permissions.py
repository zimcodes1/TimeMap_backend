# pyrefly: ignore [missing-import]
from hierarchy.models import Department, Faculty, School
from rest_framework.permissions import BasePermission


# ---------------------------------------------------------------------------
# Scope Resolvers
# ---------------------------------------------------------------------------
# These functions return querysets filtered to exactly what a user is allowed
# to see/touch. The rule: each admin level only manages the level directly
# below it. Department admins are the ONLY level that touches students &
# lecturers. Higher tiers interact exclusively with the admin tier below them.
#
#   Superuser          → everything
#   University Admin   → School Admins only
#   School Admin       → Faculty Admins in their school only
#   Faculty Admin      → Department Admins in their faculty only
#   Department Admin   → Students + Lecturers in their department only
# ---------------------------------------------------------------------------


def get_user_scope_departments(user):
    """
    Resolves department IDs visible to the user.
    Used by hierarchy/venue/scheduling/course views (not user management).

    This intentionally still gives faculty/school/university admins visibility
    into departments for scheduling and course management purposes — those
    features are cross-department by design.
    Department admins see their one department only.
    """
    if not user.is_authenticated:
        return Department.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return Department.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "university":
            return Department.objects.all()
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
    Resolves faculties visible to the user.
    Used by hierarchy/venue/scheduling/course views.
    """
    if not user.is_authenticated:
        return Faculty.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return Faculty.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "university":
            return Faculty.objects.all()
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
    Resolves schools visible to the user.
    Used by hierarchy/venue/scheduling/course views.
    """
    if not user.is_authenticated:
        return School.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return School.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "university":
            return School.objects.all()
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
                return School.objects.filter(
                    id=admin_prof.scope_department.faculty.school_id
                )
            return School.objects.none()
        return School.objects.none()

    if user.role == "student" and hasattr(user, "student_profile"):
        return School.objects.filter(
            id=user.student_profile.department.faculty.school_id
        )

    if user.role == "lecturer" and hasattr(user, "lecturer_profile"):
        return School.objects.filter(
            id=user.lecturer_profile.department.faculty.school_id
        )

    return School.objects.none()


def get_user_scope_students(user):
    """
    Resolves students accessible to a user for the User Management page.

    NEW "managers manage managers" rule:
    - ONLY department-level admins may view/manage students.
    - They see students only in their assigned scope_department.
    - All higher admin tiers (faculty, school, university) get NONE.
    - Superuser gets all.
    """
    from accounts.models import Student

    if not user.is_authenticated:
        return Student.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return Student.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "department":
            if admin_prof.scope_department:
                return Student.objects.filter(department=admin_prof.scope_department)
            return Student.objects.none()
        # Faculty, school, university admins do NOT manage students directly.
        return Student.objects.none()

    return Student.objects.none()


def get_user_scope_lecturers(user):
    """
    Resolves lecturers accessible to a user for the User Management page.

    NEW "managers manage managers" rule:
    - ONLY department-level admins may view/manage lecturers.
    - They see lecturers only in their assigned scope_department.
    - All higher admin tiers (faculty, school, university) get NONE.
    - Superuser gets all.
    """
    from accounts.models import LecturerStaff

    if not user.is_authenticated:
        return LecturerStaff.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return LecturerStaff.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile
        if admin_prof.level == "department":
            if admin_prof.scope_department:
                return LecturerStaff.objects.filter(department=admin_prof.scope_department)
            return LecturerStaff.objects.none()
        # Faculty, school, university admins do NOT manage lecturers directly.
        return LecturerStaff.objects.none()

    return LecturerStaff.objects.none()


def get_user_scope_admin_officers(user):
    """
    Resolves AdminOfficer instances visible/manageable by a user.

    NEW "managers manage managers" rule — each tier sees ONLY the tier immediately below:
    - Superuser         → all AdminOfficers (unrestricted)
    - University Admin  → School-scoped admins only
    - School Admin      → Faculty-scoped admins in their school ONLY
                          (NOT department admins — those belong to faculty admins)
    - Faculty Admin     → Department-scoped admins in their faculty ONLY
    - Department Admin  → None (they manage people, not other admins)
    """
    from accounts.models import AdminOfficer

    if not user.is_authenticated:
        return AdminOfficer.objects.none()

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return AdminOfficer.objects.all()

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile

        if admin_prof.level == "university":
            # University admins manage school-scoped admins only
            return AdminOfficer.objects.filter(level="school")

        elif admin_prof.level == "school":
            # School admins manage faculty-scoped admins within their school only
            if admin_prof.scope_school:
                return AdminOfficer.objects.filter(
                    level="faculty",
                    scope_faculty__school=admin_prof.scope_school,
                )
            return AdminOfficer.objects.none()

        elif admin_prof.level == "faculty":
            # Faculty admins manage department-scoped admins within their faculty only
            if admin_prof.scope_faculty:
                return AdminOfficer.objects.filter(
                    level="department",
                    scope_department__faculty=admin_prof.scope_faculty,
                )
            return AdminOfficer.objects.none()

        elif admin_prof.level == "department":
            # Department admins do not manage other admins
            return AdminOfficer.objects.none()

    return AdminOfficer.objects.none()


# ---------------------------------------------------------------------------
# DRF Permission Classes
# ---------------------------------------------------------------------------

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
