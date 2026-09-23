from typing import Dict, List, Set, Tuple
from django.db.models import Q

from ..models.course import CourseData
from ..models.lecturer import LecturerData
from ..models.problem import SchedulingProblem
from ..models.student_group import StudentGroup
from ..models.venue import VenueData
from .conflicts import build_student_conflict_graph
from .occurrences import expand_occurrences
from .slots import build_valid_slots
from .venues import build_allowed_venues_map


def build_scheduling_problem_from_db(
    semester_id: int | str,
    scope_type: str,
    scope_id: int | str,
) -> SchedulingProblem:
    """
    Database adapter: queries Django models for the specified scope and active semester,
    resolves courses, student cohorts, lecturer allocations, and allowed venues,
    and returns a pure-data SchedulingProblem ready for GA optimization.
    """
    from courses.models import Course, CourseAccessGrant
    from hierarchy.models import Department, Faculty, Program, School
    from scheduling.models import Semester
    from student_counts.models import ProgramStudentCount
    from venues.models import Venue

    semester = Semester.objects.select_related("session__school").get(id=semester_id)
    school = semester.session.school

    # 1. Resolve scope label
    scope_name = ""
    if scope_type == "school":
        sch = School.objects.filter(id=scope_id).first() or school
        scope_name = sch.name
    elif scope_type == "faculty":
        fac = Faculty.objects.filter(id=scope_id).first()
        scope_name = fac.name if fac else f"Faculty #{scope_id}"
    elif scope_type == "department":
        dept = Department.objects.filter(id=scope_id).first()
        scope_name = dept.name if dept else f"Department #{scope_id}"

    # 2. Query courses within scope and semester
    course_filter = Q()
    if scope_type == "school":
        course_filter = (
            Q(owning_school_id=scope_id)
            | Q(owning_faculty__school_id=scope_id)
            | Q(owning_department__faculty__school_id=scope_id)
            | Q(owning_level="general")
        )
    elif scope_type == "faculty":
        course_filter = (
            Q(owning_faculty_id=scope_id)
            | Q(owning_department__faculty_id=scope_id)
        )
    elif scope_type == "department":
        course_filter = Q(owning_department_id=scope_id)

    # Filter courses attached to this semester or without semester set
    courses_qs = (
        Course.objects.filter(course_filter)
        .filter(Q(semester=semester) | Q(semester__isnull=True))
        .select_related("owning_department", "owning_faculty", "owning_school", "target_program")
        .prefetch_related("lecturers", "access_grants")
        .distinct()
    )

    # 3. Query all programs in scope for student group resolution
    programs_map: Dict[int, Program] = {
        p.id: p for p in Program.objects.select_related("department").all()
    }
    depts_programs: Dict[int, List[Program]] = {}
    for p in programs_map.values():
        depts_programs.setdefault(p.department_id, []).append(p)

    # 4. Load student counts for headcounts
    student_counts_map: Dict[Tuple[int, int], int] = {
        (sc.program_id, sc.level): sc.count
        for sc in ProgramStudentCount.objects.all()
    }

    # 5. Build CourseData and collect lecturers
    courses_data: List[CourseData] = []
    lecturer_details: Dict[int | str, LecturerData] = {}
    lecturers_by_course: Dict[int | str, Set[int | str]] = {}

    for c in courses_qs:
        # Determine student groups taking this course
        groups: Set[StudentGroup] = set()

        if c.program_scope == "program" and c.target_program:
            tp = c.target_program
            groups.add(StudentGroup(tp.id, c.level, tp.code, tp.name))
        else:
            # General: all programs under owning department (or owning faculty/school)
            dept_ids = []
            if c.owning_department_id:
                dept_ids = [c.owning_department_id]
            elif c.owning_faculty_id:
                dept_ids = list(
                    Department.objects.filter(faculty_id=c.owning_faculty_id).values_list("id", flat=True)
                )
            elif c.owning_school_id:
                dept_ids = list(
                    Department.objects.filter(faculty__school_id=c.owning_school_id).values_list("id", flat=True)
                )

            for dept_id in dept_ids:
                for prog in depts_programs.get(dept_id, []):
                    groups.add(StudentGroup(prog.id, c.level, prog.code, prog.name))

        # Check approved access grants
        for grant in c.access_grants.filter(status="approved"):
            if grant.target_program:
                gp = grant.target_program
                groups.add(StudentGroup(gp.id, c.level, gp.code, gp.name))
            elif grant.granted_to_department_id:
                for prog in depts_programs.get(grant.granted_to_department_id, []):
                    groups.add(StudentGroup(prog.id, c.level, prog.code, prog.name))

        # Fallback if no specific program is registered
        if not groups:
            dummy_id = c.owning_department_id or 0
            groups.add(StudentGroup(dummy_id, c.level, "GEN", "General"))

        # Calculate expected headcount from ProgramStudentCounts
        total_students = sum(
            student_counts_map.get((g.program_id, g.level), 0) for g in groups
        )
        if total_students == 0:
            total_students = 50  # reasonable fallback default

        # Lecturers
        lecturer_ids_set: Set[int | str] = set()
        for lecturer in c.lecturers.all():
            lecturer_ids_set.add(lecturer.id)
            if lecturer.id not in lecturer_details:
                lecturer_details[lecturer.id] = LecturerData(
                    id=lecturer.id,
                    name=lecturer.full_name,
                    staff_id=lecturer.staff_id,
                )
        lecturers_by_course[c.id] = lecturer_ids_set

        courses_data.append(
            CourseData(
                id=c.id,
                code=c.code,
                title=c.title,
                level=c.level,
                department_id=c.owning_department_id or "",
                department_name=c.owning_department.name if c.owning_department else "",
                required_occurrences=c.required_occurrences_per_week or 1,
                course_type=c.course_type or "lecture",
                student_groups=tuple(groups),
                lecturer_ids=tuple(lecturer_ids_set),
                expected_students=total_students,
            )
        )

    # 6. Load venues in scope
    venue_filter = Q(is_active=True)
    if scope_type == "school":
        venue_filter &= (
            Q(owning_school_id=scope_id)
            | Q(owning_faculty__school_id=scope_id)
            | Q(owning_department__faculty__school_id=scope_id)
            | Q(owning_level="school")
        )
    elif scope_type == "faculty":
        venue_filter &= (
            Q(owning_faculty_id=scope_id)
            | Q(owning_department__faculty_id=scope_id)
            | Q(owning_faculty__school_id=school.id)
        )
    elif scope_type == "department":
        dept = Department.objects.filter(id=scope_id).first()
        venue_filter &= (
            Q(owning_department_id=scope_id)
            | Q(owning_faculty_id=dept.faculty_id if dept else None)
        )

    venues_qs = Venue.objects.filter(venue_filter).distinct()
    # Fallback to all active school venues if scope-specific venues are empty
    if not venues_qs.exists():
        venues_qs = Venue.objects.filter(
            Q(owning_school=school)
            | Q(owning_faculty__school_id=school.id)
            | Q(owning_department__faculty__school_id=school.id)
        ).filter(is_active=True)

    venues_data: List[VenueData] = [
        VenueData(
            id=v.id,
            name=v.name,
            venue_type=v.venue_type,
            capacity=v.capacity,
            owning_level=v.owning_level,
            owning_scope_id=v.owning_department_id or v.owning_faculty_id or v.owning_school_id or "",
        )
        for v in venues_qs
    ]

    venues_dict = {v.id: v for v in venues_data}

    # 7. Allowed venues resolution
    allowed_venues_by_course = build_allowed_venues_map(courses_data, venues_data)

    # 8. Expand course occurrences
    occurrences = expand_occurrences(courses_data)

    # 9. Build valid 24 slots (Friday 12-2 Jummat excluded)
    valid_slots = build_valid_slots()

    # 10. Build student conflict graph
    conflict_graph, shared_groups = build_student_conflict_graph(courses_data)

    return SchedulingProblem(
        occurrences=occurrences,
        valid_slots=valid_slots,
        venues=venues_dict,
        student_conflict_graph=conflict_graph,
        shared_student_groups=shared_groups,
        lecturers_by_course=lecturers_by_course,
        lecturer_details=lecturer_details,
        allowed_venues_by_course=allowed_venues_by_course,
        daily_lecture_limit=3,
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        semester_id=semester.id,
    )

