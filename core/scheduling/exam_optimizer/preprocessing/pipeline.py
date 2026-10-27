"""Preprocessing pipeline: queries Django models and builds a pure ExamSchedulingProblem."""

from typing import Any, Dict, List, Optional, Set, Tuple
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


def build_external_exam_commitments_from_db(
    semester: Semester,
    scope_type: str,
    scope_id: int,
) -> Tuple[
    Dict[int, List[Dict[str, Any]]],
    Dict[Tuple[int, int], List[Dict[str, Any]]],
    Dict[int, List[Dict[str, Any]]],
    List[Dict[str, Any]],
]:
    """
    Queries published ExamOptimizerRun instances outside the active scope for the same semester,
    and extracts:
      1. blocked_venue_windows: venue_id -> list of {date, start_time, end_time, course_code, scope}
      2. blocked_cohort_windows: (program_id, level) -> list of {date, start_time, end_time, course_code}
      3. blocked_student_windows: student_id -> list of {date, start_time, end_time, course_code}
      4. commitment_details: list of diagnostic dictionaries
    """
    from datetime import date as dt_date, time as dt_time
    from courses.models import CourseRegistration
    from hierarchy.models import Department
    from scheduling.models import ExamOptimizerRun, TimetableEntry

    blocked_venues: Dict[int, List[Dict[str, Any]]] = {}
    blocked_cohorts: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    blocked_students: Dict[int, List[Dict[str, Any]]] = {}
    details: List[Dict[str, Any]] = []

    # School-level generation: clean slate master university schedule
    if scope_type == "school":
        return blocked_venues, blocked_cohorts, blocked_students, details

    # Determine external published exam optimizer runs
    runs_qs = ExamOptimizerRun.objects.filter(
        semester=semester,
        status=ExamOptimizerRun.Status.PUBLISHED,
    )

    if scope_type == "department":
        runs_qs = runs_qs.exclude(scope_type="department", scope_id=int(scope_id))
    elif scope_type == "faculty":
        dept_ids = list(Department.objects.filter(faculty_id=scope_id).values_list("id", flat=True))
        runs_qs = runs_qs.exclude(
            Q(scope_type="faculty", scope_id=int(scope_id))
            | Q(scope_type="department", scope_id__in=dept_ids)
        )

    # Cache course students for registered courses in external runs
    external_course_ids = set()
    for run in runs_qs:
        for ev in (run.events or []):
            cid = ev.get("course_id")
            if cid:
                external_course_ids.add(cid)

    session_label = semester.session.label if hasattr(semester, "session") and semester.session else ""
    course_students_map: Dict[int, Set[int]] = {}
    if external_course_ids:
        for reg in CourseRegistration.objects.filter(
            course_id__in=external_course_ids,
            academic_session=session_label,
        ).values("course_id", "student_id"):
            course_students_map.setdefault(reg["course_id"], set()).add(reg["student_id"])

    # Ingest external events
    for run in runs_qs:
        scope_label = f"{run.scope_type.capitalize()} #{run.scope_id}"
        for ev in (run.events or []):
            try:
                ev_date = dt_date.fromisoformat(ev["date"]) if isinstance(ev["date"], str) else ev["date"]
                ev_start = dt_time.fromisoformat(ev["start_time"]) if isinstance(ev["start_time"], str) else ev["start_time"]
                ev_end = dt_time.fromisoformat(ev["end_time"]) if isinstance(ev["end_time"], str) else ev["end_time"]
            except (ValueError, KeyError, TypeError):
                continue

            course_code = ev.get("course_code", "EXAM")
            cid = ev.get("course_id")
            lvl = ev.get("course_level")
            prog_id = ev.get("program_id")

            window_info = {
                "date": ev_date,
                "start_time": ev_start,
                "end_time": ev_end,
                "course_code": course_code,
                "scope": scope_label,
            }

            # 1. Venues
            for v_entry in ev.get("venues", []):
                vid = v_entry.get("venue_id")
                if vid:
                    blocked_venues.setdefault(vid, []).append(window_info)

            # 2. Cohorts
            if prog_id and lvl:
                blocked_cohorts.setdefault((int(prog_id), int(lvl)), []).append(window_info)

            # 3. Students
            if cid and cid in course_students_map:
                for stu_id in course_students_map[cid]:
                    blocked_students.setdefault(stu_id, []).append(window_info)

            details.append({
                "source": "published_exam_run",
                "scope": scope_label,
                "course_code": course_code,
                "date": str(ev_date),
                "start_time": str(ev_start),
                "end_time": str(ev_end),
                "venues": ev.get("venues", []),
            })

    # Ingest manual TimetableEntry records of entry_type=EXAM
    manual_exams = TimetableEntry.objects.filter(
        semester=semester,
        entry_type=TimetableEntry.EntryType.EXAM,
    ).select_related("course", "venue")

    if scope_type == "department":
        manual_exams = manual_exams.exclude(course__owning_department_id=int(scope_id))
    elif scope_type == "faculty":
        dept_ids = list(Department.objects.filter(faculty_id=scope_id).values_list("id", flat=True))
        manual_exams = manual_exams.exclude(
            Q(course__owning_faculty_id=int(scope_id))
            | Q(course__owning_department_id__in=dept_ids)
        )

    for entry in manual_exams:
        m_date = entry.recurrence_start_date
        if not m_date:
            continue
        m_start = entry.start_time
        m_end = entry.end_time
        c_code = entry.course.code if entry.course else entry.title
        window_info = {
            "date": m_date,
            "start_time": m_start,
            "end_time": m_end,
            "course_code": c_code,
            "scope": "Manual Exam Booking",
        }
        if entry.venue_id:
            blocked_venues.setdefault(entry.venue_id, []).append(window_info)

        if entry.course_id and entry.course_id in course_students_map:
            for stu_id in course_students_map[entry.course_id]:
                blocked_students.setdefault(stu_id, []).append(window_info)

    return blocked_venues, blocked_cohorts, blocked_students, details


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

    # 8. Ingest external published exam commitments
    blocked_venues, blocked_cohorts, blocked_students, ext_details = (
        build_external_exam_commitments_from_db(
            semester=semester,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    )

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
        blocked_venue_windows=blocked_venues,
        blocked_cohort_windows=blocked_cohorts,
        blocked_student_windows=blocked_students,
        external_commitments_details=ext_details,
    )

