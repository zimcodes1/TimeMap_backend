"""Duration resolution logic for exam events."""

from typing import Optional, Tuple
from courses.models import Course


DEFAULT_WRITTEN_DURATION = 120
DEFAULT_CBT_DURATION = 30
DEFAULT_LAB_DURATION = 120
DEFAULT_CBT_PER_STUDENT = 30


def resolve_exam_durations(
    course: Course,
    exam_type: str,
) -> Tuple[int, Optional[int]]:
    """Resolves the nominal event duration and per-student throughput duration.

    Returns:
        (duration_minutes, per_student_minutes)
    """
    if exam_type == Course.ExamType.CBT:
        default_dur = DEFAULT_CBT_DURATION
        duration = course.exam_duration_minutes or default_dur
        per_student = (
            course.exam_duration_per_student_minutes
            or duration
            or DEFAULT_CBT_PER_STUDENT
        )
        return duration, per_student

    elif exam_type == Course.ExamType.LAB_PRACTICAL:
        duration = course.exam_duration_minutes or DEFAULT_LAB_DURATION
        per_student = course.exam_duration_per_student_minutes
        return duration, per_student

    else:
        # Written exams
        duration = course.exam_duration_minutes or DEFAULT_WRITTEN_DURATION
        per_student = course.exam_duration_per_student_minutes
        return duration, per_student

