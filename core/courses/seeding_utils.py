"""
Shared utility module for seeding faculty courses, access grants, and inter-departmental
course relationships in TimeMapper for NSUK.

Enforces:
1. Reusing existing common courses (e.g., GST111, MTH101, PHY101) without code duplication.
2. Generating approved CourseAccessGrant instances for cross-departmental sharing.
3. Level course caps (100L: max 10, 200L: max 8, 300L: max 7, 400L: max 6, 500L+: max 6).
4. Association with the current active semester.
"""

from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone

from accounts.models import AdminOfficer
from courses.models import Course, CourseAccessGrant
from hierarchy.models import Department, Faculty, Program, School
from scheduling.models import Semester


def get_active_semester(school: Optional[School] = None) -> Optional[Semester]:
    """Resolves the currently active semester for the school."""
    qs = Semester.objects.filter(is_active=True)
    if school:
        qs = qs.filter(session__school=school)
    sem = qs.first()
    if not sem:
        sem = Semester.objects.filter(session__school=school).order_by("-start_date").first()
    if not sem:
        sem = Semester.objects.filter(is_active=True).first() or Semester.objects.first()
    return sem


def ensure_general_studies_courses(
    school: School,
    active_semester: Semester,
    admin_officer: Optional[AdminOfficer] = None,
) -> Dict[str, Course]:
    """
    Ensures university-wide General Studies (GST) courses are present for the active semester.
    Reuses existing records without duplication.
    """
    gst_definitions = [
        # (code, title, level, occurrences, exam_type, duration_mins)
        ("GST111", "Communication in English I", 100, 2, Course.ExamType.CBT, 60),
        ("GST113", "Nigerian Peoples and Culture", 100, 1, Course.ExamType.CBT, 60),
        ("GST115", "Use of Library & Study Skills", 100, 1, Course.ExamType.CBT, 60),
        ("GST211", "Philosophy, Logic & Human Existence", 200, 1, Course.ExamType.CBT, 60),
        ("GST221", "Peace Studies & Conflict Resolution", 200, 1, Course.ExamType.CBT, 60),
        ("GST311", "Entrepreneurship and Innovation", 300, 2, Course.ExamType.CBT, 60),
    ]

    gst_courses = {}
    for code, title, level, occurrences, exam_type, duration in gst_definitions:
        course, created = Course.objects.get_or_create(
            code=code,
            defaults={
                "title": title,
                "level": level,
                "course_type": Course.CourseType.LECTURE,
                "required_occurrences_per_week": occurrences,
                "exam_type": exam_type,
                "exam_duration_minutes": duration,
                "owning_level": Course.OwningLevel.GENERAL,
                "owning_school": school,
                "semester": active_semester,
                "program_scope": Course.ProgramScope.GENERAL,
            },
        )
        if not created and not course.semester:
            course.semester = active_semester
            course.save(update_fields=["semester"])
        gst_courses[code] = course

    return gst_courses


def ensure_course(
    code: str,
    title: str,
    level: int,
    department: Optional[Department],
    faculty: Faculty,
    school: School,
    active_semester: Semester,
    course_type: str = Course.CourseType.LECTURE,
    occurrences: int = 2,
    exam_type: str = Course.ExamType.WRITTEN,
    exam_duration: int = 120,
    target_program: Optional[Program] = None,
    program_scope: str = Course.ProgramScope.GENERAL,
) -> Tuple[Course, bool]:
    """
    Creates or retrieves a course, ensuring it is linked to the active semester
    and properly configured with department/faculty ownership.
    """
    code_clean = code.strip().upper()
    course = Course.objects.filter(code=code_clean).first()
    if course:
        # Course already exists, ensure semester association
        updated = False
        if not course.semester:
            course.semester = active_semester
            updated = True
        if updated:
            course.save(update_fields=["semester"])
        return course, False

    # Create new course record
    course = Course.objects.create(
        code=code_clean,
        title=title,
        level=level,
        course_type=course_type,
        required_occurrences_per_week=occurrences,
        exam_type=exam_type,
        exam_duration_minutes=exam_duration,
        owning_level=Course.OwningLevel.DEPARTMENT if department else Course.OwningLevel.FACULTY,
        owning_department=department,
        owning_faculty=faculty,
        owning_school=school,
        semester=active_semester,
        program_scope=Course.ProgramScope.PROGRAM if target_program else program_scope,
        target_program=target_program,
    )
    return course, True


def grant_course_access(
    course: Course,
    department: Department,
    target_program: Optional[Program] = None,
    initiated_by: Optional[AdminOfficer] = None,
    decided_by: Optional[AdminOfficer] = None,
) -> Tuple[Optional[CourseAccessGrant], bool]:
    """
    Grants approved access to an external or common course for a target department
    or specific degree program.
    """
    # If the course is already directly owned by this department without a program restriction,
    # a department grant is redundant
    if (
        course.owning_department_id == department.id
        and course.program_scope == Course.ProgramScope.GENERAL
        and target_program is None
    ):
        return None, False

    # If it's owned by the department but program-scoped, and target_program matches target_program,
    # default ownership covers it
    if (
        course.owning_department_id == department.id
        and course.target_program_id == (target_program.id if target_program else None)
    ):
        return None, False

    grant_scope = (
        CourseAccessGrant.GrantScope.PROGRAM
        if target_program
        else CourseAccessGrant.GrantScope.GENERAL
    )

    grant, created = CourseAccessGrant.objects.get_or_create(
        course=course,
        granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
        granted_to_department=department,
        target_program=target_program,
        defaults={
            "direction": CourseAccessGrant.Direction.OFFERED,
            "status": CourseAccessGrant.Status.APPROVED,
            "initiated_by": initiated_by,
            "decided_by": decided_by or initiated_by,
            "decided_at": timezone.now(),
            "grant_scope": grant_scope,
        },
    )

    if not created and grant.status != CourseAccessGrant.Status.APPROVED:
        grant.status = CourseAccessGrant.Status.APPROVED
        grant.decided_by = decided_by or initiated_by
        grant.decided_at = timezone.now()
        grant.save(update_fields=["status", "decided_by", "decided_at"])

    return grant, created


def resolve_scope_admins(school: School, faculty: Faculty) -> Tuple[Optional[AdminOfficer], Optional[AdminOfficer], Dict[str, AdminOfficer]]:
    """Resolves School Admin, Faculty Admin, and Department Admins map."""
    school_admin = AdminOfficer.objects.filter(scope_school=school).first()
    if not school_admin:
        school_admin = AdminOfficer.objects.filter(level=AdminOfficer.Level.SCHOOL).first()

    fac_admin = AdminOfficer.objects.filter(scope_faculty=faculty).first()

    dept_admins = {}
    for d in faculty.departments.all():
        d_admin = AdminOfficer.objects.filter(scope_department=d).first()
        if d_admin:
            dept_admins[d.code] = d_admin

    return school_admin, fac_admin, dept_admins

