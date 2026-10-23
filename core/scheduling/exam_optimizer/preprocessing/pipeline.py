"""Preprocessing pipeline: queries Django models and builds a pure ExamSchedulingProblem."""

from typing import List, Optional
from django.db.models import Q

from courses.models import Course
from hierarchy.models import Department, Faculty, School
from scheduling.models import Semester

from ..models.problem import ExamSchedulingProblem
from ..models.time_window import CalendarPolicy
from .calendar import build_candidate_windows
from .conflicts import build_exam_conflict_graph
from .populations import resolve_course_populations
from .venues import filter_venues_by_exam_type, resolve_scope_venues


def build_exam_problem_from_db(
    semester: Semester,
    scope_type: str,
    scope_id: int,
    policy: Optional[CalendarPolicy] = None,
) -> ExamSchedulingProblem:
    """Extracts raw academic data from the database and constructs a pure-data ExamSchedulingProblem.

    Validates the semester examination period, loads courses matching the administrative scope,
    resolves eligible venues, precomputes the exact student conflict graph, and formats candidate windows.
    """
    start, end = semester.exam_start_date, semester.exam_end_date
    if not start or not end or start >= end:
        raise ValueError(
            "A valid semester examination period must be configured before optimization."
        )

    pol = policy or CalendarPolicy()

    # 1. Resolve scope label
    scope_name = ""
    if scope_type == "department":
        dept = Department.objects.filter(pk=scope_id).first()
        scope_name = dept.name if dept else f"Department #{scope_id}"
    elif scope_type == "faculty":
        fac = Faculty.objects.filter(pk=scope_id).first()
        scope_name = fac.name if fac else f"Faculty #{scope_id}"
    elif scope_type == "school":
        sch = School.objects.filter(pk=scope_id).first() or getattr(
            semester.session, "school", None
        )
        scope_name = sch.name if sch else f"School #{scope_id}"
    else:
        raise ValueError(f"Unknown examination scope type: {scope_type}")

    # 2. Query scoped courses attached to this semester
    courses_qs = Course.objects.filter(
        Q(semester=semester) | Q(semester__isnull=True)
    ).select_related(
        "owning_department__faculty",
        "owning_faculty",
        "owning_school",
        "target_program",
    )

    from courses.models import CourseAccessGrant

    if scope_type == "department":
        department = Department.objects.select_related("faculty__school").get(pk=scope_id)
        granted_course_ids = list(
            CourseAccessGrant.objects.filter(
                status=CourseAccessGrant.Status.APPROVED,
                granted_to_department_id=scope_id,
            ).values_list("course_id", flat=True)
        )
        courses_qs = courses_qs.filter(
            Q(owning_department_id=scope_id)
            | Q(id__in=granted_course_ids)
            | Q(owning_level=Course.OwningLevel.FACULTY, owning_faculty=department.faculty)
            | Q(owning_level__in=[Course.OwningLevel.SCHOOL, Course.OwningLevel.GENERAL], owning_school=department.faculty.school)
        )
    elif scope_type == "faculty":
        faculty = Faculty.objects.select_related("school").get(pk=scope_id)
        granted_course_ids = list(
            CourseAccessGrant.objects.filter(
                status=CourseAccessGrant.Status.APPROVED,
            ).filter(
                Q(granted_to_faculty_id=scope_id) | Q(granted_to_department__faculty_id=scope_id)
            ).values_list("course_id", flat=True)
        )
        courses_qs = courses_qs.filter(
            Q(owning_faculty_id=scope_id)
            | Q(owning_department__faculty_id=scope_id)
            | Q(owning_level__in=[Course.OwningLevel.SCHOOL, Course.OwningLevel.GENERAL], owning_school=faculty.school)
            | Q(id__in=granted_course_ids)
        )
    elif scope_type == "school":
        courses_qs = courses_qs.filter(
            Q(owning_school_id=scope_id)
            | Q(owning_faculty__school_id=scope_id)
            | Q(owning_department__faculty__school_id=scope_id)
            | Q(owning_level=Course.OwningLevel.GENERAL)
        )

    courses: List[Course] = list(courses_qs.distinct())

    # 3. Resolve accessible venues and partition by exam type
    all_venues = resolve_scope_venues(scope_type, scope_id)
    venues_by_type = {
        exam_type: filter_venues_by_exam_type(all_venues, exam_type)
        for exam_type in Course.ExamType.values
    }

    # 4. Precompute student registrations and exact conflict graph
    students_by_course, conflict_graph, cohort_overlaps = build_exam_conflict_graph(
        courses, semester
    )

    # 5. Build logical ExamEvent objects
    events = resolve_course_populations(courses, students_by_course, conflict_graph)

    # 6. Calculate venue scarcity per event
    for event in events.values():
        eligible = venues_by_type.get(event.exam_type, [])
        event.venue_scarcity = 1.0 / len(eligible) if eligible else 1.0

    # 7. Collect unique durations and generate candidate windows
    unique_durations = list(set(e.duration_minutes for e in events.values()))
    if not unique_durations:
        unique_durations = [120]

    candidate_windows = build_candidate_windows(start, end, unique_durations, pol)

    session_label = semester.session.label if hasattr(semester, "session") and semester.session else ""

    return ExamSchedulingProblem(
        semester_id=semester.id,
        semester_label=session_label,
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        start_date=start,
        end_date=end,
        events=events,
        venues_by_type=venues_by_type,
        student_conflict_graph=conflict_graph,
        cohort_overlaps=cohort_overlaps,
        candidate_windows=candidate_windows,
        policy=pol,
    )

