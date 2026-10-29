"""
Shared utility module for seeding realistic student populations (ProgramStudentCount)
in TimeMapper for degree programs across faculties.
"""

from typing import Dict, Optional, Tuple
from accounts.models import AdminOfficer
from hierarchy.models import Department, Faculty, Program, School
from student_counts.models import ProgramStudentCount


def resolve_program_admin(program: Program) -> Optional[AdminOfficer]:
    """Resolves the most specific AdminOfficer for a given degree program."""
    dept = program.department
    if dept:
        dept_admin = AdminOfficer.objects.filter(scope_department=dept).first()
        if dept_admin:
            return dept_admin
        faculty = dept.faculty
        if faculty:
            fac_admin = AdminOfficer.objects.filter(scope_faculty=faculty).first()
            if fac_admin:
                return fac_admin
            school = faculty.school
            if school:
                return AdminOfficer.objects.filter(scope_school=school).first()
    return AdminOfficer.objects.first()


def seed_program_student_counts(
    program: Program,
    levels_dict: Dict[int, int],
    admin: Optional[AdminOfficer] = None,
) -> int:
    """
    Creates or updates ProgramStudentCount records for the specified program across levels.
    Returns the count of created or updated records.
    """
    if admin is None:
        admin = resolve_program_admin(program)

    count_records = 0
    for level, headcount in levels_dict.items():
        ProgramStudentCount.objects.update_or_create(
            program=program,
            level=level,
            defaults={
                "count": headcount,
                "updated_by": admin,
            },
        )
        count_records += 1

    return count_records

