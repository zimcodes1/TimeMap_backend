from django.db.models import Q
from .models import Course, CourseAccessGrant


def get_visible_courses_for_student(student):
    """
    Returns a queryset of Course objects visible to a student.
    Visibility rules:
    1. Active semester: only courses for currently active semesters are visible to students.
    2. Default ownership:
       - 'department': student's home department matches course.owning_department.
         If course.program_scope == 'program', must match student.program.
       - 'faculty': student's faculty matches course.owning_faculty
       - 'school': student's school matches course.owning_school
       - 'general': visible to everyone
    3. Approved access grants:
       - 'approved' CourseAccessGrant granted to student's department, faculty, or school.
         If grant.grant_scope == 'program', must match student.program.
    """
    if not student or not hasattr(student, "department"):
        return Course.objects.none()

    dept = student.department
    fac = dept.faculty
    sch = fac.school
    prog = getattr(student, "program", None)

    # 1. Program match condition for department-level courses
    program_filter = Q(program_scope=Course.ProgramScope.GENERAL)
    if prog:
        program_filter |= Q(program_scope=Course.ProgramScope.PROGRAM, target_program=prog)

    # 2. Default ownership matches
    default_q = (
        Q(owning_level=Course.OwningLevel.GENERAL)
        | (Q(owning_level=Course.OwningLevel.DEPARTMENT, owning_department=dept) & program_filter)
        | Q(owning_level=Course.OwningLevel.FACULTY, owning_faculty=fac)
        | Q(owning_level=Course.OwningLevel.SCHOOL, owning_school=sch)
    )

    # 3. Approved grants
    grant_program_filter = Q(grant_scope=CourseAccessGrant.GrantScope.GENERAL)
    if prog:
        grant_program_filter |= Q(grant_scope=CourseAccessGrant.GrantScope.PROGRAM, target_program=prog)

    approved_grant_course_ids = CourseAccessGrant.objects.filter(
        status=CourseAccessGrant.Status.APPROVED
    ).filter(
        (Q(granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT, granted_to_department=dept) & grant_program_filter)
        | Q(granted_to_level=CourseAccessGrant.GrantedToLevel.FACULTY, granted_to_faculty=fac)
        | Q(granted_to_level=CourseAccessGrant.GrantedToLevel.SCHOOL, granted_to_school=sch)
    ).values_list("course_id", flat=True)

    qs = Course.objects.filter(default_q | Q(id__in=approved_grant_course_ids))

    # Only show active semester courses (or courses without semester assigned)
    qs = qs.filter(Q(semester__is_active=True) | Q(semester__isnull=True))

    return qs.distinct()
