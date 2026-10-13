"""Course population aggregation and logical exam event construction."""

from typing import Dict, List, Set
from courses.models import Course
from courses.services import calculate_course_student_count

from ..models.event import ExamEvent, ExamPopulation
from .durations import resolve_exam_durations


def resolve_course_populations(
    courses: List[Course],
    students_by_course: Dict[int, Set[int | str]],
    conflict_graph: Dict[int, Set[int]],
) -> Dict[int, ExamEvent]:
    """Constructs normalized logical ExamEvent objects from course data.

    Calculates effective student counts by taking the maximum of explicit student registrations
    and program student headcount estimates.
    """
    events: Dict[int, ExamEvent] = {}

    for course in courses:
        registered_students = students_by_course.get(course.id, set())
        estimated_count = calculate_course_student_count(course)
        effective_count = max(len(registered_students), estimated_count)

        exam_type = course.exam_type or Course.ExamType.WRITTEN
        duration, per_student = resolve_exam_durations(course, exam_type)

        department = course.owning_department or (
            course.target_program.department if course.target_program_id else None
        )

        population = ExamPopulation(
            course_id=course.id,
            department_id=department.id if department else None,
            department_name=department.name if department else None,
            program_id=course.target_program_id,
            program_name=course.target_program.name if course.target_program_id else None,
            level=course.level,
            student_count=effective_count,
            student_ids=registered_students,
        )

        conflict_deg = len(conflict_graph.get(course.id, set()))

        event = ExamEvent(
            course_id=course.id,
            course_code=course.code,
            course_title=course.title,
            course_level=course.level,
            exam_type=exam_type,
            duration_minutes=duration,
            duration_per_student_minutes=per_student,
            student_count=effective_count,
            student_ids=registered_students,
            populations=[population],
            department_id=department.id if department else None,
            department_name=department.name if department else None,
            program_id=course.target_program_id,
            program_name=course.target_program.name if course.target_program_id else None,
            conflict_degree=conflict_deg,
            venue_scarcity=0.0,
        )
        events[course.id] = event

    return events

