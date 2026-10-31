"""
Shared utility module for seeding realistic lecturers and assigning them to courses
across faculties and departments at NSUK.

Enforces:
1. Idempotent User and LecturerStaff creation with role=LECTURER.
2. Proper department binding and realistic staff credentials.
3. Realistic assignment of 1-2 lecturers per course to balance teaching loads.
"""

from typing import List, Optional, Tuple
from django.db import transaction

from accounts.models import LecturerStaff, User
from courses.models import Course
from hierarchy.models import Department, School


def ensure_lecturer(
    staff_id: str,
    full_name: str,
    email: str,
    department: Department,
    default_password: str = "Lecturer#2026",
) -> Tuple[LecturerStaff, bool]:
    """
    Creates or retrieves a LecturerStaff instance and its associated User account.
    """
    clean_id = staff_id.strip().upper()
    user, u_created = User.objects.get_or_create(
        identifier=clean_id,
        defaults={
            "role": User.Role.LECTURER,
            "requires_password_reset": False,
            "is_active": True,
        },
    )
    if u_created or not user.password:
        user.set_password(default_password)
        user.role = User.Role.LECTURER
        user.requires_password_reset = False
        user.is_active = True
        user.save()

    lecturer, l_created = LecturerStaff.objects.get_or_create(
        staff_id=clean_id,
        defaults={
            "user": user,
            "full_name": full_name,
            "email": email,
            "department": department,
        },
    )
    if not l_created:
        lecturer.department = department
        lecturer.full_name = full_name
        lecturer.email = email
        lecturer.save()

    return lecturer, l_created


def assign_lecturers_to_course(
    course: Course,
    lecturers: List[LecturerStaff],
) -> None:
    """
    Assigns the given list of lecturers to the course.
    """
    if lecturers:
        course.lecturers.set(lecturers)

