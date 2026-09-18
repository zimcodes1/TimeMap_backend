from django.db.models import Q, Sum
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


def get_course_attributed_programs(course, hierarchy_ctx=None):
    """
    Returns a set of Program IDs attributed to the course:
    1. Originating department / scope:
       - If course is program-scoped (program_scope == 'program') and target_program is set,
         returns {target_program_id}.
       - If general scope:
         - Owning department: all programs under the owning department.
         - Owning faculty: all programs under departments in the owning faculty.
         - Owning school: all programs under departments in faculties in the owning school.
         - Owning general: all programs in the institution.
    2. Granted access (approved grants only):
       - If grant is program-scoped (grant_scope == 'program') or target_program is set,
         adds target_program_id.
       - If general scope:
         - Granted to department: all programs under that department.
         - Granted to faculty: all programs under departments in that faculty.
         - Granted to school: all programs under departments in faculties in that school.
    """
    from hierarchy.models import Program

    if hierarchy_ctx:
        depts_programs = hierarchy_ctx.get("depts_programs", {})
        fac_depts = hierarchy_ctx.get("fac_depts", {})
        sch_depts = hierarchy_ctx.get("sch_depts", {})
        all_program_ids = hierarchy_ctx.get("all_program_ids", set())
    else:
        depts_programs = {}
        fac_depts = {}
        sch_depts = {}
        all_program_ids = set()
        for p in Program.objects.select_related("department__faculty").all():
            all_program_ids.add(p.id)
            depts_programs.setdefault(p.department_id, []).append(p.id)
            if p.department and p.department.faculty_id:
                fac_depts.setdefault(p.department.faculty_id, set()).add(p.department_id)
                if p.department.faculty.school_id:
                    sch_depts.setdefault(p.department.faculty.school_id, set()).add(p.department_id)

    attributed_programs = set()

    # 1. Originating department / program scope
    if course.program_scope == Course.ProgramScope.PROGRAM and course.target_program_id:
        attributed_programs.add(course.target_program_id)
    else:
        if course.owning_department_id:
            attributed_programs.update(depts_programs.get(course.owning_department_id, []))
        elif course.owning_faculty_id:
            for d_id in fac_depts.get(course.owning_faculty_id, set()):
                attributed_programs.update(depts_programs.get(d_id, []))
        elif course.owning_school_id:
            for d_id in sch_depts.get(course.owning_school_id, set()):
                attributed_programs.update(depts_programs.get(d_id, []))
        elif course.owning_level == Course.OwningLevel.GENERAL:
            attributed_programs.update(all_program_ids)

    # 2. Approved access grants
    if hasattr(course, "_prefetched_objects_cache") and "access_grants" in course._prefetched_objects_cache:
        grants = [g for g in course.access_grants.all() if g.status == CourseAccessGrant.Status.APPROVED]
    else:
        grants = list(course.access_grants.filter(status=CourseAccessGrant.Status.APPROVED))

    for grant in grants:
        if grant.grant_scope == CourseAccessGrant.GrantScope.PROGRAM or grant.target_program_id:
            if grant.target_program_id:
                attributed_programs.add(grant.target_program_id)
        else:
            if grant.granted_to_department_id:
                attributed_programs.update(depts_programs.get(grant.granted_to_department_id, []))
            elif grant.granted_to_faculty_id:
                for d_id in fac_depts.get(grant.granted_to_faculty_id, set()):
                    attributed_programs.update(depts_programs.get(d_id, []))
            elif grant.granted_to_school_id:
                for d_id in sch_depts.get(grant.granted_to_school_id, set()):
                    attributed_programs.update(depts_programs.get(d_id, []))

    return attributed_programs


def calculate_course_student_count(course, hierarchy_ctx=None):
    """
    Calculates the total student headcount attributed to this course across both
    the originating department/programs and any other departments/programs with approved access grants.
    Cascades to Student model records or student_registrations if ProgramStudentCount is not set.
    """
    from student_counts.models import ProgramStudentCount
    from accounts.models import Student

    attributed_programs = get_course_attributed_programs(course, hierarchy_ctx=hierarchy_ctx)

    if hierarchy_ctx and "student_counts_map" in hierarchy_ctx:
        student_counts_map = hierarchy_ctx["student_counts_map"]
        total = sum(student_counts_map.get((pid, course.level), 0) for pid in attributed_programs)
    else:
        total = (
            ProgramStudentCount.objects.filter(
                program_id__in=attributed_programs,
                level=course.level,
            ).aggregate(total=Sum("count"))["total"]
            or 0
        )

    if total > 0:
        return total

    # Fallback 1: Count individual student accounts in attributed programs at course level
    if attributed_programs:
        student_qs_count = Student.objects.filter(
            program_id__in=attributed_programs,
            level=course.level,
        ).count()
        if student_qs_count > 0:
            return student_qs_count

    # Fallback 2: Direct course registrations
    reg_count = course.student_registrations.count()
    if reg_count > 0:
        return reg_count

    return 0


def annotate_courses_with_student_counts(courses):
    """
    Precomputes and attaches `_cached_registration_count` to each course in `courses`.
    Loads all program mappings and ProgramStudentCount records once in batch.
    """
    from student_counts.models import ProgramStudentCount
    from hierarchy.models import Program

    courses_list = list(courses)
    if not courses_list:
        return

    depts_programs = {}
    fac_depts = {}
    sch_depts = {}
    all_program_ids = set()

    for p in Program.objects.select_related("department__faculty").all():
        all_program_ids.add(p.id)
        depts_programs.setdefault(p.department_id, []).append(p.id)
        if p.department and p.department.faculty_id:
            fac_depts.setdefault(p.department.faculty_id, set()).add(p.department_id)
            if p.department.faculty.school_id:
                sch_depts.setdefault(p.department.faculty.school_id, set()).add(p.department_id)

    student_counts_map = {
        (sc["program_id"], sc["level"]): sc["count"]
        for sc in ProgramStudentCount.objects.values("program_id", "level", "count")
    }

    hierarchy_ctx = {
        "depts_programs": depts_programs,
        "fac_depts": fac_depts,
        "sch_depts": sch_depts,
        "all_program_ids": all_program_ids,
        "student_counts_map": student_counts_map,
    }

    for c in courses_list:
        c._cached_registration_count = calculate_course_student_count(c, hierarchy_ctx=hierarchy_ctx)

